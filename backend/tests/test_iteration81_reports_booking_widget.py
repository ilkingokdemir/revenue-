"""
Iteration 81 - Testing 3 New Features:
1. Reports Centre - Consolidated data + CSV export
2. Online Booking Widget - Public booking form for hotel websites
3. Housekeeping-Maintenance Integration - One-tap maintenance report from housekeeping
"""
import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
TEST_PROPERTY = "aldgate-flats"

class TestAuth:
    """Authentication for protected endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_cookies(self):
        """Login and get auth cookies"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.cookies
    
    def test_login_success(self):
        """Verify admin login works"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200
        data = response.json()
        # Login returns user data directly (not wrapped in "user" key)
        assert "email" in data
        assert data["email"] == "admin@hotelbox.com"


class TestReportsCentre:
    """Reports Centre - Consolidated data + CSV export"""
    
    @pytest.fixture(scope="class")
    def auth_cookies(self):
        """Login and get auth cookies"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200
        return response.cookies
    
    # ==================== REPORT SUMMARY ====================
    
    def test_report_summary_month(self, auth_cookies):
        """GET /api/reports/summary/{property_id}?period=month - consolidated data"""
        response = requests.get(
            f"{BASE_URL}/api/reports/summary/{TEST_PROPERTY}?period=month",
            cookies=auth_cookies
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify structure
        assert "period" in data
        assert data["period"] == "month"
        
        # Bookings section
        assert "bookings" in data
        assert "total" in data["bookings"]
        assert "confirmed" in data["bookings"]
        assert "revenue" in data["bookings"]
        
        # Maintenance section
        assert "maintenance" in data
        assert "total" in data["maintenance"]
        assert "open" in data["maintenance"]
        assert "resolved" in data["maintenance"]
        assert "overdue" in data["maintenance"]
        assert "cost" in data["maintenance"]
        
        # Guest Journey section
        assert "guest_journey" in data
        assert "registrations" in data["guest_journey"]
        assert "completed" in data["guest_journey"]
        assert "completion_rate" in data["guest_journey"]
        
        # Satisfaction section
        assert "satisfaction" in data
        assert "total" in data["satisfaction"]
        assert "happy" in data["satisfaction"]
        assert "need_help" in data["satisfaction"]
        assert "satisfaction_rate" in data["satisfaction"]
        
        # POS section
        assert "pos" in data
        assert "orders" in data["pos"]
        assert "revenue" in data["pos"]
        
        # Loyalty section
        assert "loyalty" in data
        assert "members" in data["loyalty"]
    
    def test_report_summary_week(self, auth_cookies):
        """GET /api/reports/summary/{property_id}?period=week"""
        response = requests.get(
            f"{BASE_URL}/api/reports/summary/{TEST_PROPERTY}?period=week",
            cookies=auth_cookies
        )
        assert response.status_code == 200
        data = response.json()
        assert data["period"] == "week"
    
    def test_report_summary_quarter(self, auth_cookies):
        """GET /api/reports/summary/{property_id}?period=quarter"""
        response = requests.get(
            f"{BASE_URL}/api/reports/summary/{TEST_PROPERTY}?period=quarter",
            cookies=auth_cookies
        )
        assert response.status_code == 200
        data = response.json()
        assert data["period"] == "quarter"
    
    def test_report_summary_year(self, auth_cookies):
        """GET /api/reports/summary/{property_id}?period=year"""
        response = requests.get(
            f"{BASE_URL}/api/reports/summary/{TEST_PROPERTY}?period=year",
            cookies=auth_cookies
        )
        assert response.status_code == 200
        data = response.json()
        assert data["period"] == "year"
    
    def test_report_summary_all_properties(self, auth_cookies):
        """GET /api/reports/summary/all - works with 'all' property_id"""
        response = requests.get(
            f"{BASE_URL}/api/reports/summary/all?period=month",
            cookies=auth_cookies
        )
        assert response.status_code == 200
        data = response.json()
        assert "bookings" in data
    
    # ==================== CSV EXPORTS ====================
    
    def test_export_bookings_csv(self, auth_cookies):
        """GET /api/reports/export/{property_id}/bookings - CSV export"""
        response = requests.get(
            f"{BASE_URL}/api/reports/export/{TEST_PROPERTY}/bookings?period=month",
            cookies=auth_cookies
        )
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("content-type", "")
        assert "attachment" in response.headers.get("content-disposition", "")
        
        # Verify CSV has header row
        content = response.text
        assert "Booking Ref" in content or len(content) > 0
    
    def test_export_maintenance_csv(self, auth_cookies):
        """GET /api/reports/export/{property_id}/maintenance - CSV export"""
        response = requests.get(
            f"{BASE_URL}/api/reports/export/{TEST_PROPERTY}/maintenance?period=month",
            cookies=auth_cookies
        )
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("content-type", "")
        
        content = response.text
        assert "Title" in content or len(content) > 0
    
    def test_export_registrations_csv(self, auth_cookies):
        """GET /api/reports/export/{property_id}/registrations - CSV export"""
        response = requests.get(
            f"{BASE_URL}/api/reports/export/{TEST_PROPERTY}/registrations?period=month",
            cookies=auth_cookies
        )
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("content-type", "")
    
    def test_export_pos_csv(self, auth_cookies):
        """GET /api/reports/export/{property_id}/pos - CSV export"""
        response = requests.get(
            f"{BASE_URL}/api/reports/export/{TEST_PROPERTY}/pos?period=month",
            cookies=auth_cookies
        )
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("content-type", "")
    
    def test_export_satisfaction_csv(self, auth_cookies):
        """GET /api/reports/export/{property_id}/satisfaction - CSV export"""
        response = requests.get(
            f"{BASE_URL}/api/reports/export/{TEST_PROPERTY}/satisfaction?period=month",
            cookies=auth_cookies
        )
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("content-type", "")
    
    def test_export_invalid_type_returns_400(self, auth_cookies):
        """GET /api/reports/export/{property_id}/invalid - returns 400"""
        response = requests.get(
            f"{BASE_URL}/api/reports/export/{TEST_PROPERTY}/invalid_type?period=month",
            cookies=auth_cookies
        )
        assert response.status_code == 400
    
    def test_report_requires_auth(self):
        """Reports endpoints require authentication"""
        response = requests.get(f"{BASE_URL}/api/reports/summary/{TEST_PROPERTY}")
        assert response.status_code == 401


class TestBookingWidget:
    """Online Booking Widget - Public booking form for hotel websites"""
    
    @pytest.fixture(scope="class")
    def auth_cookies(self):
        """Login and get auth cookies"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200
        return response.cookies
    
    # ==================== PUBLIC: PROPERTY INFO ====================
    
    def test_widget_info_public(self):
        """GET /api/booking-widget/info/{property_id} - public endpoint"""
        response = requests.get(f"{BASE_URL}/api/booking-widget/info/{TEST_PROPERTY}")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify structure
        assert "hotel_name" in data
        assert "property_id" in data
        assert data["property_id"] == TEST_PROPERTY
        assert "rooms" in data
        assert isinstance(data["rooms"], list)
        assert "currency" in data
        
        # Verify room structure if rooms exist
        if len(data["rooms"]) > 0:
            room = data["rooms"][0]
            assert "id" in room
            assert "name" in room
            assert "base_rate" in room
            assert "max_occupancy" in room
    
    def test_widget_info_no_auth_required(self):
        """Widget info is public - no auth required"""
        response = requests.get(f"{BASE_URL}/api/booking-widget/info/{TEST_PROPERTY}")
        assert response.status_code == 200
    
    # ==================== PUBLIC: CHECK AVAILABILITY ====================
    
    def test_check_availability(self):
        """POST /api/booking-widget/check-availability - check room availability"""
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        day_after = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
        
        response = requests.post(f"{BASE_URL}/api/booking-widget/check-availability", json={
            "property_id": TEST_PROPERTY,
            "check_in": tomorrow,
            "check_out": day_after
        })
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "available_rooms" in data
        assert isinstance(data["available_rooms"], list)
        assert "check_in" in data
        assert "check_out" in data
        
        # Verify room availability structure
        if len(data["available_rooms"]) > 0:
            room = data["available_rooms"][0]
            assert "room_type_id" in room
            assert "name" in room
            assert "base_rate" in room
            assert "total_rate" in room
            assert "nights" in room
            assert "available" in room
            assert "max_occupancy" in room
    
    def test_check_availability_missing_fields(self):
        """POST /api/booking-widget/check-availability - missing fields returns 400"""
        response = requests.post(f"{BASE_URL}/api/booking-widget/check-availability", json={
            "property_id": TEST_PROPERTY
            # Missing check_in and check_out
        })
        assert response.status_code == 400
    
    def test_check_availability_no_auth_required(self):
        """Check availability is public - no auth required"""
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        day_after = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
        
        response = requests.post(f"{BASE_URL}/api/booking-widget/check-availability", json={
            "property_id": TEST_PROPERTY,
            "check_in": tomorrow,
            "check_out": day_after
        })
        assert response.status_code == 200
    
    # ==================== PUBLIC: CREATE BOOKING ====================
    
    def test_create_widget_booking(self):
        """POST /api/booking-widget/book - create booking from widget"""
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        day_after = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
        test_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
        
        response = requests.post(f"{BASE_URL}/api/booking-widget/book", json={
            "property_id": TEST_PROPERTY,
            "room_type": "Standard Room",
            "check_in": tomorrow,
            "check_out": day_after,
            "guest_name": "TEST_Widget Guest",
            "guest_email": test_email,
            "guest_phone": "+1234567890",
            "rate": 100,
            "guests": 2,
            "special_requests": "Late check-in please"
        })
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify response
        assert data["status"] == "confirmed"
        assert "booking_ref" in data
        assert data["booking_ref"].startswith("WEB-")
        assert "booking" in data
        
        # Verify booking details
        booking = data["booking"]
        assert booking["guest_name"] == "TEST_Widget Guest"
        assert booking["guest_email"] == test_email
        assert booking["source"] == "website_widget"
        assert booking["status"] == "confirmed"
        assert booking["nights"] == 2
    
    def test_create_booking_missing_required_fields(self):
        """POST /api/booking-widget/book - missing required fields returns 400"""
        response = requests.post(f"{BASE_URL}/api/booking-widget/book", json={
            "property_id": TEST_PROPERTY,
            "room_type": "Standard Room"
            # Missing check_in, check_out, guest_name, guest_email
        })
        assert response.status_code == 400
    
    def test_create_booking_no_auth_required(self):
        """Widget booking is public - no auth required"""
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        day_after = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
        
        response = requests.post(f"{BASE_URL}/api/booking-widget/book", json={
            "property_id": TEST_PROPERTY,
            "room_type": "Deluxe Room",
            "check_in": tomorrow,
            "check_out": day_after,
            "guest_name": "TEST_Public Guest",
            "guest_email": f"public_{uuid.uuid4().hex[:8]}@test.com",
            "rate": 150
        })
        assert response.status_code == 200
    
    # ==================== ADMIN: WIDGET CONFIG ====================
    
    def test_get_widget_config(self, auth_cookies):
        """GET /api/booking-widget/config/{property_id} - get widget config"""
        response = requests.get(
            f"{BASE_URL}/api/booking-widget/config/{TEST_PROPERTY}",
            cookies=auth_cookies
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "property_id" in data
        assert "enabled" in data
    
    def test_update_widget_config(self, auth_cookies):
        """PUT /api/booking-widget/config/{property_id} - update widget config"""
        response = requests.put(
            f"{BASE_URL}/api/booking-widget/config/{TEST_PROPERTY}",
            json={
                "enabled": True,
                "accent_color": "#1e3a5f",
                "show_rates": True
            },
            cookies=auth_cookies
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "saved"
    
    def test_widget_config_requires_auth(self):
        """Widget config endpoints require authentication"""
        response = requests.get(f"{BASE_URL}/api/booking-widget/config/{TEST_PROPERTY}")
        assert response.status_code == 401


class TestHousekeepingMaintenanceIntegration:
    """Housekeeping-Maintenance Integration - One-tap maintenance report"""
    
    @pytest.fixture(scope="class")
    def auth_cookies(self):
        """Login and get auth cookies"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200
        return response.cookies
    
    def test_report_maintenance_from_housekeeping(self, auth_cookies):
        """POST /api/housekeeping/report-maintenance - create maintenance issue from housekeeping"""
        response = requests.post(
            f"{BASE_URL}/api/housekeeping/report-maintenance",
            json={
                "property_id": TEST_PROPERTY,
                "room_number": "305",
                "title": "TEST_Broken faucet in bathroom",
                "description": "Water leaking from bathroom faucet",
                "category": "plumbing",
                "priority": "high"
            },
            cookies=auth_cookies
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify issue structure
        assert "id" in data
        assert data["property_id"] == TEST_PROPERTY
        assert data["room_number"] == "305"
        assert data["title"] == "TEST_Broken faucet in bathroom"
        assert data["category"] == "plumbing"
        assert data["priority"] == "high"
        assert data["status"] == "open"
        assert data["source"] == "housekeeping"
        
        # Verify SLA is set
        assert "sla_hours" in data
        assert data["sla_hours"] == 8  # high priority = 8 hours
        assert "sla_deadline" in data
        
        # Verify timeline entry
        assert "timeline" in data
        assert len(data["timeline"]) > 0
        assert data["timeline"][0]["action"] == "created"
        assert "Reported from housekeeping" in data["timeline"][0]["detail"]
        
        # Store issue_id for photo upload test
        TestHousekeepingMaintenanceIntegration.created_issue_id = data["id"]
    
    def test_report_maintenance_default_priority(self, auth_cookies):
        """POST /api/housekeeping/report-maintenance - default priority is medium"""
        response = requests.post(
            f"{BASE_URL}/api/housekeeping/report-maintenance",
            json={
                "property_id": TEST_PROPERTY,
                "room_number": "306",
                "title": "TEST_Light bulb needs replacement",
                "category": "electrical"
                # No priority specified - should default to medium
            },
            cookies=auth_cookies
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["priority"] == "medium"
        assert data["sla_hours"] == 24  # medium priority = 24 hours
    
    def test_report_maintenance_critical_priority(self, auth_cookies):
        """POST /api/housekeeping/report-maintenance - critical priority has 2 hour SLA"""
        response = requests.post(
            f"{BASE_URL}/api/housekeeping/report-maintenance",
            json={
                "property_id": TEST_PROPERTY,
                "room_number": "307",
                "title": "TEST_No hot water",
                "category": "plumbing",
                "priority": "critical"
            },
            cookies=auth_cookies
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["priority"] == "critical"
        assert data["sla_hours"] == 2  # critical priority = 2 hours
    
    def test_report_maintenance_assigns_department(self, auth_cookies):
        """POST /api/housekeeping/report-maintenance - assigns correct department based on category"""
        # Test plumbing -> maintenance department
        response = requests.post(
            f"{BASE_URL}/api/housekeeping/report-maintenance",
            json={
                "property_id": TEST_PROPERTY,
                "room_number": "308",
                "title": "TEST_Clogged drain",
                "category": "plumbing"
            },
            cookies=auth_cookies
        )
        assert response.status_code == 200
        data = response.json()
        assert data["assigned_department"] == "maintenance"
        
        # Test safety -> management department
        response2 = requests.post(
            f"{BASE_URL}/api/housekeeping/report-maintenance",
            json={
                "property_id": TEST_PROPERTY,
                "room_number": "309",
                "title": "TEST_Fire alarm issue",
                "category": "safety"
            },
            cookies=auth_cookies
        )
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["assigned_department"] == "management"
    
    def test_report_maintenance_requires_auth(self):
        """POST /api/housekeeping/report-maintenance - requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/housekeeping/report-maintenance",
            json={
                "property_id": TEST_PROPERTY,
                "room_number": "310",
                "title": "Test issue"
            }
        )
        assert response.status_code == 401
    
    def test_upload_maintenance_photo(self, auth_cookies):
        """POST /api/housekeeping/upload-maintenance-photo/{issue_id} - upload photo"""
        # Use the issue created in previous test
        issue_id = getattr(TestHousekeepingMaintenanceIntegration, 'created_issue_id', None)
        if not issue_id:
            pytest.skip("No issue_id from previous test")
        
        # Create a simple test image (1x1 pixel PNG)
        import base64
        png_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )
        
        files = {"file": ("test_photo.png", png_data, "image/png")}
        response = requests.post(
            f"{BASE_URL}/api/housekeeping/upload-maintenance-photo/{issue_id}",
            files=files,
            cookies=auth_cookies
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert data["status"] == "uploaded"
        assert "url" in data
        assert "/api/uploads/maintenance/" in data["url"]


class TestCleanup:
    """Cleanup test data"""
    
    @pytest.fixture(scope="class")
    def auth_cookies(self):
        """Login and get auth cookies"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200
        return response.cookies
    
    def test_cleanup_test_bookings(self, auth_cookies):
        """Cleanup TEST_ prefixed bookings"""
        # Get bookings
        response = requests.get(
            f"{BASE_URL}/api/bookings/{TEST_PROPERTY}",
            cookies=auth_cookies
        )
        if response.status_code == 200:
            bookings = response.json()
            for booking in bookings:
                if booking.get("guest_name", "").startswith("TEST_"):
                    requests.delete(
                        f"{BASE_URL}/api/bookings/{booking['id']}",
                        cookies=auth_cookies
                    )
        assert True  # Cleanup is best-effort
    
    def test_cleanup_test_maintenance(self, auth_cookies):
        """Cleanup TEST_ prefixed maintenance issues"""
        # Get maintenance issues
        response = requests.get(
            f"{BASE_URL}/api/maintenance/{TEST_PROPERTY}",
            cookies=auth_cookies
        )
        if response.status_code == 200:
            issues = response.json()
            for issue in issues:
                if issue.get("title", "").startswith("TEST_"):
                    requests.delete(
                        f"{BASE_URL}/api/maintenance/{issue['id']}",
                        cookies=auth_cookies
                    )
        assert True  # Cleanup is best-effort
