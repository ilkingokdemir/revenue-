"""
Iteration 80 - Testing 3 New Features:
1. Enhanced Maintenance Dashboard (trends, SLA compliance, team workload, top locations)
2. Guest QR Maintenance Reports (public endpoints for guest issue reporting)
3. Rate Manager (dynamic pricing with day multipliers, occupancy rules, seasons)
"""
import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://review-hub-108.preview.emergentagent.com').rstrip('/')
API = f"{BASE_URL}/api"

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
TEST_PROPERTY_ID = "aldgate-flats"
TEST_ROOM_ID = "301"


@pytest.fixture(scope="module")
def auth_session():
    """Create authenticated session for admin user"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Login
    response = session.post(f"{API}/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    print(f"✓ Logged in as {ADMIN_EMAIL}")
    return session


@pytest.fixture(scope="module")
def public_session():
    """Create unauthenticated session for public endpoints"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


# ==================== ENHANCED MAINTENANCE DASHBOARD TESTS ====================

class TestMaintenanceDashboard:
    """Test GET /api/maintenance/dashboard/{property_id}"""
    
    def test_dashboard_endpoint_exists(self, auth_session):
        """Dashboard endpoint returns 200"""
        response = auth_session.get(f"{API}/maintenance/dashboard/{TEST_PROPERTY_ID}")
        assert response.status_code == 200, f"Dashboard failed: {response.text}"
        print("✓ Dashboard endpoint accessible")
    
    def test_dashboard_monthly_trends(self, auth_session):
        """Dashboard returns monthly_trends array with 6 months"""
        response = auth_session.get(f"{API}/maintenance/dashboard/{TEST_PROPERTY_ID}")
        data = response.json()
        
        assert "monthly_trends" in data, "Missing monthly_trends"
        assert isinstance(data["monthly_trends"], list), "monthly_trends should be array"
        assert len(data["monthly_trends"]) == 6, f"Expected 6 months, got {len(data['monthly_trends'])}"
        
        # Check structure of each month
        for month in data["monthly_trends"]:
            assert "month" in month, "Missing month field"
            assert "created" in month, "Missing created count"
            assert "resolved" in month, "Missing resolved count"
        
        print(f"✓ Monthly trends: {[m['month'] for m in data['monthly_trends']]}")
    
    def test_dashboard_sla_compliance(self, auth_session):
        """Dashboard returns SLA compliance rate"""
        response = auth_session.get(f"{API}/maintenance/dashboard/{TEST_PROPERTY_ID}")
        data = response.json()
        
        assert "sla_compliance_rate" in data, "Missing sla_compliance_rate"
        assert "sla_total" in data, "Missing sla_total"
        assert "sla_breached" in data, "Missing sla_breached"
        
        # Rate should be 0-100
        assert 0 <= data["sla_compliance_rate"] <= 100, f"Invalid SLA rate: {data['sla_compliance_rate']}"
        
        print(f"✓ SLA compliance: {data['sla_compliance_rate']}% ({data['sla_total']} total, {data['sla_breached']} breached)")
    
    def test_dashboard_avg_resolution_hours(self, auth_session):
        """Dashboard returns average resolution time in hours"""
        response = auth_session.get(f"{API}/maintenance/dashboard/{TEST_PROPERTY_ID}")
        data = response.json()
        
        assert "avg_resolution_hours" in data, "Missing avg_resolution_hours"
        assert isinstance(data["avg_resolution_hours"], (int, float)), "avg_resolution_hours should be numeric"
        
        print(f"✓ Avg resolution time: {data['avg_resolution_hours']} hours")
    
    def test_dashboard_team_workload(self, auth_session):
        """Dashboard returns team workload dict"""
        response = auth_session.get(f"{API}/maintenance/dashboard/{TEST_PROPERTY_ID}")
        data = response.json()
        
        assert "team_workload" in data, "Missing team_workload"
        assert isinstance(data["team_workload"], dict), "team_workload should be dict"
        
        print(f"✓ Team workload: {data['team_workload']}")
    
    def test_dashboard_top_locations(self, auth_session):
        """Dashboard returns top locations array"""
        response = auth_session.get(f"{API}/maintenance/dashboard/{TEST_PROPERTY_ID}")
        data = response.json()
        
        assert "top_locations" in data, "Missing top_locations"
        assert isinstance(data["top_locations"], list), "top_locations should be array"
        
        # Check structure if any locations exist
        for loc in data["top_locations"]:
            assert "location" in loc, "Missing location field"
            assert "count" in loc, "Missing count field"
        
        print(f"✓ Top locations: {data['top_locations'][:5]}")
    
    def test_dashboard_all_properties(self, auth_session):
        """Dashboard works with property_id='all'"""
        response = auth_session.get(f"{API}/maintenance/dashboard/all")
        assert response.status_code == 200, f"Dashboard 'all' failed: {response.text}"
        
        data = response.json()
        assert "monthly_trends" in data
        assert "sla_compliance_rate" in data
        
        print("✓ Dashboard works with 'all' properties")


# ==================== GUEST QR MAINTENANCE REPORT TESTS ====================

class TestGuestQRMaintenance:
    """Test public guest maintenance report endpoints"""
    
    def test_guest_report_info_public(self, public_session):
        """GET /api/maintenance/guest-report-info/{property_id}/{room_id} is public"""
        response = public_session.get(f"{API}/maintenance/guest-report-info/{TEST_PROPERTY_ID}/{TEST_ROOM_ID}")
        assert response.status_code == 200, f"Guest report info failed: {response.text}"
        
        data = response.json()
        assert "hotel_name" in data, "Missing hotel_name"
        assert "room" in data, "Missing room"
        assert "property_id" in data, "Missing property_id"
        assert data["room"] == TEST_ROOM_ID, f"Room mismatch: {data['room']}"
        
        print(f"✓ Guest report info: {data['hotel_name']} - Room {data['room']}")
    
    def test_guest_report_submit_public(self, public_session):
        """POST /api/maintenance/guest-report/{property_id}/{room_id} creates issue"""
        test_title = f"TEST_Guest_Report_{uuid.uuid4().hex[:8]}"
        
        response = public_session.post(
            f"{API}/maintenance/guest-report/{TEST_PROPERTY_ID}/{TEST_ROOM_ID}",
            json={
                "title": test_title,
                "description": "AC not cooling properly",
                "category": "hvac",
                "guest_name": "John Guest",
                "guest_email": "john@guest.com"
            }
        )
        assert response.status_code == 200, f"Guest report submit failed: {response.text}"
        
        data = response.json()
        assert "status" in data, "Missing status"
        assert data["status"] == "submitted", f"Unexpected status: {data['status']}"
        assert "id" in data, "Missing issue id"
        
        print(f"✓ Guest report submitted: {data['id']}")
        return data["id"]
    
    def test_guest_report_creates_high_priority(self, public_session, auth_session):
        """Guest reports are created with high priority"""
        test_title = f"TEST_Priority_Check_{uuid.uuid4().hex[:8]}"
        
        # Submit guest report
        response = public_session.post(
            f"{API}/maintenance/guest-report/{TEST_PROPERTY_ID}/{TEST_ROOM_ID}",
            json={
                "title": test_title,
                "description": "Test priority",
                "category": "plumbing"
            }
        )
        issue_id = response.json()["id"]
        
        # Verify issue details
        detail_response = auth_session.get(f"{API}/maintenance/issues/detail/{issue_id}")
        assert detail_response.status_code == 200
        
        issue = detail_response.json()
        assert issue["priority"] == "high", f"Expected high priority, got {issue['priority']}"
        assert issue["source"] == "guest_qr", f"Expected source=guest_qr, got {issue.get('source')}"
        assert issue["room_number"] == TEST_ROOM_ID
        
        print(f"✓ Guest report has high priority and source=guest_qr")
        
        # Cleanup
        auth_session.delete(f"{API}/maintenance/issues/{issue_id}")
    
    def test_guest_report_timeline_entry(self, public_session, auth_session):
        """Guest report creates timeline entry with guest name"""
        test_title = f"TEST_Timeline_{uuid.uuid4().hex[:8]}"
        guest_name = "Alice Guest"
        
        response = public_session.post(
            f"{API}/maintenance/guest-report/{TEST_PROPERTY_ID}/{TEST_ROOM_ID}",
            json={
                "title": test_title,
                "description": "Test timeline",
                "category": "electrical",
                "guest_name": guest_name
            }
        )
        issue_id = response.json()["id"]
        
        # Check timeline
        detail_response = auth_session.get(f"{API}/maintenance/issues/detail/{issue_id}")
        issue = detail_response.json()
        
        assert "timeline" in issue, "Missing timeline"
        assert len(issue["timeline"]) >= 1, "Timeline should have at least 1 entry"
        
        first_entry = issue["timeline"][0]
        assert first_entry["action"] == "created"
        assert guest_name in first_entry["by"], f"Guest name not in timeline: {first_entry['by']}"
        
        print(f"✓ Timeline entry created by guest: {first_entry['by']}")
        
        # Cleanup
        auth_session.delete(f"{API}/maintenance/issues/{issue_id}")
    
    def test_guest_upload_photo_public(self, public_session, auth_session):
        """POST /api/maintenance/guest-upload-photo/{issue_id} uploads photo"""
        # First create a guest report
        test_title = f"TEST_Photo_Upload_{uuid.uuid4().hex[:8]}"
        
        response = public_session.post(
            f"{API}/maintenance/guest-report/{TEST_PROPERTY_ID}/{TEST_ROOM_ID}",
            json={
                "title": test_title,
                "description": "Test photo upload",
                "category": "furniture"
            }
        )
        issue_id = response.json()["id"]
        
        # Create a simple test image (1x1 pixel PNG)
        import base64
        import io
        png_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )
        
        # Upload photo - use a fresh session without Content-Type header for multipart
        upload_session = requests.Session()
        files = {"file": ("test.png", io.BytesIO(png_data), "image/png")}
        upload_response = upload_session.post(
            f"{API}/maintenance/guest-upload-photo/{issue_id}",
            files=files
        )
        assert upload_response.status_code == 200, f"Photo upload failed: {upload_response.text}"
        
        upload_data = upload_response.json()
        assert upload_data["status"] == "uploaded"
        assert "url" in upload_data
        
        # Verify photo in issue
        detail_response = auth_session.get(f"{API}/maintenance/issues/detail/{issue_id}")
        issue = detail_response.json()
        
        assert len(issue["photos_before"]) >= 1, "Photo not added to photos_before"
        assert issue["photos_before"][0]["uploaded_by"] == "Guest"
        
        print(f"✓ Guest photo uploaded: {upload_data['url']}")
        
        # Cleanup
        auth_session.delete(f"{API}/maintenance/issues/{issue_id}")
    
    def test_guest_upload_requires_guest_qr_source(self, public_session, auth_session):
        """Guest photo upload only works for guest_qr source issues"""
        # Create a staff-reported issue (not guest_qr)
        staff_issue = auth_session.post(f"{API}/maintenance/issues", json={
            "title": f"TEST_Staff_Issue_{uuid.uuid4().hex[:8]}",
            "description": "Staff reported",
            "property_id": TEST_PROPERTY_ID,
            "category": "general"
        })
        staff_issue_id = staff_issue.json()["id"]
        
        # Try to upload as guest - should fail
        import base64
        import io
        png_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )
        
        # Use a fresh session without Content-Type header for multipart
        upload_session = requests.Session()
        files = {"file": ("test.png", io.BytesIO(png_data), "image/png")}
        
        upload_response = upload_session.post(
            f"{API}/maintenance/guest-upload-photo/{staff_issue_id}",
            files=files
        )
        assert upload_response.status_code == 404, "Should reject non-guest_qr issues"
        
        print("✓ Guest upload correctly rejects non-guest_qr issues")
        
        # Cleanup
        auth_session.delete(f"{API}/maintenance/issues/{staff_issue_id}")


# ==================== RATE MANAGER TESTS ====================

class TestRateManagerPlans:
    """Test Rate Manager CRUD for rate plans"""
    
    def test_list_rate_plans(self, auth_session):
        """GET /api/rate-manager/plans/{property_id} returns list"""
        response = auth_session.get(f"{API}/rate-manager/plans/{TEST_PROPERTY_ID}")
        assert response.status_code == 200, f"List plans failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Should return array"
        
        print(f"✓ Rate plans list: {len(data)} plans")
    
    def test_create_rate_plan(self, auth_session):
        """POST /api/rate-manager/plans creates plan with day multipliers"""
        plan_name = f"TEST_Plan_{uuid.uuid4().hex[:8]}"
        
        response = auth_session.post(f"{API}/rate-manager/plans", json={
            "property_id": TEST_PROPERTY_ID,
            "name": plan_name,
            "room_type": "Deluxe",
            "base_rate": 150,
            "currency": "GBP",
            "min_rate": 100,
            "max_rate": 300,
            "day_multipliers": {
                "monday": 1.0,
                "tuesday": 1.0,
                "wednesday": 1.0,
                "thursday": 1.0,
                "friday": 1.2,
                "saturday": 1.3,
                "sunday": 1.1
            },
            "occupancy_rules": [
                {"threshold": 50, "adjustment": 0},
                {"threshold": 70, "adjustment": 10},
                {"threshold": 85, "adjustment": 25},
                {"threshold": 95, "adjustment": 50}
            ]
        })
        assert response.status_code == 200, f"Create plan failed: {response.text}"
        
        plan = response.json()
        assert plan["name"] == plan_name
        assert plan["base_rate"] == 150
        assert plan["day_multipliers"]["saturday"] == 1.3
        assert len(plan["occupancy_rules"]) == 4
        assert "id" in plan
        
        print(f"✓ Rate plan created: {plan['id']}")
        return plan["id"]
    
    def test_update_rate_plan(self, auth_session):
        """PUT /api/rate-manager/plans/{plan_id} updates plan"""
        # Create plan first
        plan_name = f"TEST_Update_{uuid.uuid4().hex[:8]}"
        create_response = auth_session.post(f"{API}/rate-manager/plans", json={
            "property_id": TEST_PROPERTY_ID,
            "name": plan_name,
            "base_rate": 100
        })
        plan_id = create_response.json()["id"]
        
        # Update
        update_response = auth_session.put(f"{API}/rate-manager/plans/{plan_id}", json={
            "base_rate": 200,
            "name": f"{plan_name}_Updated"
        })
        assert update_response.status_code == 200, f"Update failed: {update_response.text}"
        
        updated = update_response.json()
        assert updated["base_rate"] == 200
        assert "Updated" in updated["name"]
        
        print(f"✓ Rate plan updated: base_rate=200")
        
        # Cleanup
        auth_session.delete(f"{API}/rate-manager/plans/{plan_id}")
    
    def test_delete_rate_plan(self, auth_session):
        """DELETE /api/rate-manager/plans/{plan_id} deletes plan"""
        # Create plan
        create_response = auth_session.post(f"{API}/rate-manager/plans", json={
            "property_id": TEST_PROPERTY_ID,
            "name": f"TEST_Delete_{uuid.uuid4().hex[:8]}",
            "base_rate": 100
        })
        plan_id = create_response.json()["id"]
        
        # Delete
        delete_response = auth_session.delete(f"{API}/rate-manager/plans/{plan_id}")
        assert delete_response.status_code == 200
        assert delete_response.json()["status"] == "deleted"
        
        # Verify deleted
        list_response = auth_session.get(f"{API}/rate-manager/plans/{TEST_PROPERTY_ID}")
        plans = list_response.json()
        assert not any(p["id"] == plan_id for p in plans), "Plan should be deleted"
        
        print("✓ Rate plan deleted")


class TestRateCalculation:
    """Test rate calculation endpoint"""
    
    @pytest.fixture
    def test_plan(self, auth_session):
        """Create a test plan for calculation tests"""
        response = auth_session.post(f"{API}/rate-manager/plans", json={
            "property_id": TEST_PROPERTY_ID,
            "name": f"TEST_Calc_{uuid.uuid4().hex[:8]}",
            "base_rate": 100,
            "currency": "GBP",
            "day_multipliers": {
                "monday": 1.0,
                "tuesday": 1.0,
                "wednesday": 1.0,
                "thursday": 1.0,
                "friday": 1.2,
                "saturday": 1.5,
                "sunday": 1.1
            },
            "occupancy_rules": [
                {"threshold": 50, "adjustment": 0},
                {"threshold": 70, "adjustment": 10},
                {"threshold": 85, "adjustment": 25}
            ],
            "min_rate": 80,
            "max_rate": 200
        })
        plan = response.json()
        yield plan
        # Cleanup
        auth_session.delete(f"{API}/rate-manager/plans/{plan['id']}")
    
    def test_calculate_rate_basic(self, auth_session, test_plan):
        """POST /api/rate-manager/calculate returns calculated rate"""
        response = auth_session.post(f"{API}/rate-manager/calculate", json={
            "plan_id": test_plan["id"],
            "date": "2026-01-20",  # Monday
            "occupancy_pct": 50
        })
        assert response.status_code == 200, f"Calculate failed: {response.text}"
        
        data = response.json()
        assert "base_rate" in data
        assert "calculated_rate" in data
        assert "day_multiplier" in data
        assert "occupancy_pct" in data
        assert "occupancy_adjustment_pct" in data
        assert "currency" in data
        
        # Monday with 50% occupancy = base rate (100 * 1.0 * 1.0 = 100)
        assert data["base_rate"] == 100
        assert data["day_multiplier"] == 1.0
        
        print(f"✓ Rate calculated: {data['currency']} {data['calculated_rate']}")
    
    def test_calculate_rate_weekend_multiplier(self, auth_session, test_plan):
        """Weekend multiplier increases rate"""
        # Saturday = 1.5x multiplier
        response = auth_session.post(f"{API}/rate-manager/calculate", json={
            "plan_id": test_plan["id"],
            "date": "2026-01-24",  # Saturday
            "occupancy_pct": 50
        })
        data = response.json()
        
        assert data["day_multiplier"] == 1.5
        # 100 * 1.5 = 150
        assert data["calculated_rate"] == 150
        
        print(f"✓ Saturday rate: {data['calculated_rate']} (1.5x multiplier)")
    
    def test_calculate_rate_occupancy_adjustment(self, auth_session, test_plan):
        """High occupancy increases rate"""
        # 85% occupancy = +25% adjustment
        response = auth_session.post(f"{API}/rate-manager/calculate", json={
            "plan_id": test_plan["id"],
            "date": "2026-01-20",  # Monday
            "occupancy_pct": 85
        })
        data = response.json()
        
        assert data["occupancy_adjustment_pct"] == 25
        # 100 * 1.0 * 1.25 = 125
        assert data["calculated_rate"] == 125
        
        print(f"✓ High occupancy rate: {data['calculated_rate']} (+25% adjustment)")
    
    def test_calculate_rate_combined(self, auth_session, test_plan):
        """Combined weekend + high occupancy"""
        # Saturday (1.5x) + 85% occupancy (+25%)
        response = auth_session.post(f"{API}/rate-manager/calculate", json={
            "plan_id": test_plan["id"],
            "date": "2026-01-24",  # Saturday
            "occupancy_pct": 85
        })
        data = response.json()
        
        # 100 * 1.5 * 1.25 = 187.5
        assert data["calculated_rate"] == 187.5
        
        print(f"✓ Combined rate: {data['calculated_rate']} (weekend + high occupancy)")
    
    def test_calculate_rate_max_cap(self, auth_session, test_plan):
        """Rate capped at max_rate"""
        # Saturday (1.5x) + 95% occupancy (would be +50% if rule existed)
        # But we only have up to 85% rule, so +25%
        # 100 * 1.5 * 1.25 = 187.5 (under 200 max)
        response = auth_session.post(f"{API}/rate-manager/calculate", json={
            "plan_id": test_plan["id"],
            "date": "2026-01-24",
            "occupancy_pct": 95
        })
        data = response.json()
        
        assert data["calculated_rate"] <= 200, f"Rate should be capped at 200, got {data['calculated_rate']}"
        
        print(f"✓ Rate respects max cap: {data['calculated_rate']} <= 200")


class TestRateCalendar:
    """Test 30-day rate calendar endpoint"""
    
    @pytest.fixture
    def test_plan(self, auth_session):
        """Create a test plan for calendar tests"""
        response = auth_session.post(f"{API}/rate-manager/plans", json={
            "property_id": TEST_PROPERTY_ID,
            "name": f"TEST_Calendar_{uuid.uuid4().hex[:8]}",
            "base_rate": 100,
            "currency": "GBP",
            "day_multipliers": {
                "monday": 1.0, "tuesday": 1.0, "wednesday": 1.0,
                "thursday": 1.0, "friday": 1.2, "saturday": 1.3, "sunday": 1.1
            },
            "occupancy_rules": [
                {"threshold": 50, "adjustment": 0},
                {"threshold": 70, "adjustment": 10}
            ]
        })
        plan = response.json()
        yield plan
        auth_session.delete(f"{API}/rate-manager/plans/{plan['id']}")
    
    def test_calendar_returns_30_days(self, auth_session, test_plan):
        """GET /api/rate-manager/calendar/{plan_id} returns 30 days"""
        response = auth_session.get(f"{API}/rate-manager/calendar/{test_plan['id']}")
        assert response.status_code == 200, f"Calendar failed: {response.text}"
        
        data = response.json()
        assert "plan_name" in data
        assert "currency" in data
        assert "days" in data
        assert len(data["days"]) == 30, f"Expected 30 days, got {len(data['days'])}"
        
        print(f"✓ Calendar has 30 days for plan: {data['plan_name']}")
    
    def test_calendar_day_structure(self, auth_session, test_plan):
        """Each calendar day has required fields"""
        response = auth_session.get(f"{API}/rate-manager/calendar/{test_plan['id']}")
        data = response.json()
        
        for day in data["days"]:
            assert "date" in day, "Missing date"
            assert "day" in day, "Missing day name"
            assert "is_weekend" in day, "Missing is_weekend"
            assert "base_rate" in day, "Missing base_rate"
            assert "calculated_rate" in day, "Missing calculated_rate"
            assert "multiplier" in day, "Missing multiplier"
            assert "est_occupancy" in day, "Missing est_occupancy"
        
        print("✓ All calendar days have required fields")
    
    def test_calendar_weekend_detection(self, auth_session, test_plan):
        """Calendar correctly marks weekends"""
        response = auth_session.get(f"{API}/rate-manager/calendar/{test_plan['id']}")
        data = response.json()
        
        weekends = [d for d in data["days"] if d["is_weekend"]]
        weekdays = [d for d in data["days"] if not d["is_weekend"]]
        
        # Should have some weekends and weekdays
        assert len(weekends) > 0, "Should have weekend days"
        assert len(weekdays) > 0, "Should have weekday days"
        
        # Weekend days should have higher multipliers
        for weekend in weekends:
            assert weekend["multiplier"] >= 1.1, f"Weekend multiplier too low: {weekend['multiplier']}"
        
        print(f"✓ Calendar has {len(weekends)} weekend days, {len(weekdays)} weekdays")
    
    def test_calendar_not_found(self, auth_session):
        """Calendar returns 404 for non-existent plan"""
        response = auth_session.get(f"{API}/rate-manager/calendar/non-existent-plan-id")
        assert response.status_code == 404
        
        print("✓ Calendar returns 404 for invalid plan")


class TestRateSeasons:
    """Test Rate Manager seasons CRUD"""
    
    def test_list_seasons(self, auth_session):
        """GET /api/rate-manager/seasons/{property_id} returns list"""
        response = auth_session.get(f"{API}/rate-manager/seasons/{TEST_PROPERTY_ID}")
        assert response.status_code == 200, f"List seasons failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list)
        
        print(f"✓ Seasons list: {len(data)} seasons")
    
    def test_create_season(self, auth_session):
        """POST /api/rate-manager/seasons creates season"""
        season_name = f"TEST_Season_{uuid.uuid4().hex[:8]}"
        
        response = auth_session.post(f"{API}/rate-manager/seasons", json={
            "property_id": TEST_PROPERTY_ID,
            "name": season_name,
            "start_date": "2026-06-01",
            "end_date": "2026-08-31",
            "adjustment_pct": 30,
            "color": "#ff6b6b"
        })
        assert response.status_code == 200, f"Create season failed: {response.text}"
        
        season = response.json()
        assert season["name"] == season_name
        assert season["adjustment_pct"] == 30
        assert season["start_date"] == "2026-06-01"
        assert season["end_date"] == "2026-08-31"
        assert "id" in season
        
        print(f"✓ Season created: {season['name']} (+{season['adjustment_pct']}%)")
        
        # Cleanup
        auth_session.delete(f"{API}/rate-manager/seasons/{season['id']}")
    
    def test_delete_season(self, auth_session):
        """DELETE /api/rate-manager/seasons/{season_id} deletes season"""
        # Create season
        create_response = auth_session.post(f"{API}/rate-manager/seasons", json={
            "property_id": TEST_PROPERTY_ID,
            "name": f"TEST_Delete_{uuid.uuid4().hex[:8]}",
            "start_date": "2026-12-20",
            "end_date": "2026-12-31",
            "adjustment_pct": 50
        })
        season_id = create_response.json()["id"]
        
        # Delete
        delete_response = auth_session.delete(f"{API}/rate-manager/seasons/{season_id}")
        assert delete_response.status_code == 200
        assert delete_response.json()["status"] == "deleted"
        
        print("✓ Season deleted")


# ==================== CLEANUP ====================

class TestCleanup:
    """Cleanup test data"""
    
    def test_cleanup_test_issues(self, auth_session):
        """Remove TEST_ prefixed maintenance issues"""
        response = auth_session.get(f"{API}/maintenance/issues/{TEST_PROPERTY_ID}")
        issues = response.json()
        
        test_issues = [i for i in issues if i.get("title", "").startswith("TEST_")]
        for issue in test_issues:
            auth_session.delete(f"{API}/maintenance/issues/{issue['id']}")
        
        print(f"✓ Cleaned up {len(test_issues)} test issues")
    
    def test_cleanup_test_plans(self, auth_session):
        """Remove TEST_ prefixed rate plans"""
        response = auth_session.get(f"{API}/rate-manager/plans/{TEST_PROPERTY_ID}")
        plans = response.json()
        
        test_plans = [p for p in plans if p.get("name", "").startswith("TEST_")]
        for plan in test_plans:
            auth_session.delete(f"{API}/rate-manager/plans/{plan['id']}")
        
        print(f"✓ Cleaned up {len(test_plans)} test rate plans")
    
    def test_cleanup_test_seasons(self, auth_session):
        """Remove TEST_ prefixed seasons"""
        response = auth_session.get(f"{API}/rate-manager/seasons/{TEST_PROPERTY_ID}")
        seasons = response.json()
        
        test_seasons = [s for s in seasons if s.get("name", "").startswith("TEST_")]
        for season in test_seasons:
            auth_session.delete(f"{API}/rate-manager/seasons/{season['id']}")
        
        print(f"✓ Cleaned up {len(test_seasons)} test seasons")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
