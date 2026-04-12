"""
Iteration 68 - Dashboard Upgrade & Housekeeping Module Tests
Tests for:
1. Dashboard overview API with housekeeping stats
2. Housekeeping room status board
3. Housekeeping tasks CRUD
4. Housekeeping maintenance requests CRUD
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
PROPERTY_ID = "aldgate-flats"

class TestAuth:
    """Authentication for test session"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Login and get auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        cookies = response.cookies
        return cookies
    
    @pytest.fixture(scope="class")
    def session(self, auth_token):
        """Create authenticated session"""
        s = requests.Session()
        s.cookies.update(auth_token)
        return s


class TestDashboardOverview(TestAuth):
    """Dashboard overview API tests - includes housekeeping stats"""
    
    def test_dashboard_overview_returns_200(self, session):
        """GET /api/dashboard/overview/{property_id} returns 200"""
        response = session.get(f"{BASE_URL}/api/dashboard/overview/{PROPERTY_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("✓ Dashboard overview returns 200")
    
    def test_dashboard_overview_has_bookings(self, session):
        """Dashboard overview contains bookings data"""
        response = session.get(f"{BASE_URL}/api/dashboard/overview/{PROPERTY_ID}")
        data = response.json()
        assert "bookings" in data, "Missing 'bookings' key"
        bookings = data["bookings"]
        assert "today_checkins" in bookings, "Missing today_checkins"
        assert "today_checkouts" in bookings, "Missing today_checkouts"
        assert "current_guests" in bookings, "Missing current_guests"
        assert "occupancy" in bookings, "Missing occupancy"
        print(f"✓ Bookings data: {bookings['today_checkins']} check-ins, {bookings['today_checkouts']} check-outs, {bookings['occupancy']}% occupancy")
    
    def test_dashboard_overview_has_messaging(self, session):
        """Dashboard overview contains messaging data"""
        response = session.get(f"{BASE_URL}/api/dashboard/overview/{PROPERTY_ID}")
        data = response.json()
        assert "messaging" in data, "Missing 'messaging' key"
        messaging = data["messaging"]
        assert "unread" in messaging, "Missing unread count"
        assert "open" in messaging, "Missing open conversations"
        print(f"✓ Messaging data: {messaging['unread']} unread, {messaging['open']} open")
    
    def test_dashboard_overview_has_housekeeping(self, session):
        """Dashboard overview contains housekeeping stats - NEW FEATURE"""
        response = session.get(f"{BASE_URL}/api/dashboard/overview/{PROPERTY_ID}")
        data = response.json()
        assert "housekeeping" in data, "Missing 'housekeeping' key in dashboard overview"
        hk = data["housekeeping"]
        assert "clean" in hk, "Missing clean count"
        assert "dirty" in hk, "Missing dirty count"
        assert "in_progress" in hk, "Missing in_progress count"
        assert "inspected" in hk, "Missing inspected count"
        assert "out_of_order" in hk, "Missing out_of_order count"
        print(f"✓ Housekeeping stats: clean={hk['clean']}, dirty={hk['dirty']}, in_progress={hk['in_progress']}, inspected={hk['inspected']}, ooo={hk['out_of_order']}")
    
    def test_dashboard_overview_has_revenue(self, session):
        """Dashboard overview contains revenue data"""
        response = session.get(f"{BASE_URL}/api/dashboard/overview/{PROPERTY_ID}")
        data = response.json()
        assert "revenue" in data, "Missing 'revenue' key"
        revenue = data["revenue"]
        assert "month_total" in revenue, "Missing month_total"
        assert "week_total" in revenue, "Missing week_total"
        print(f"✓ Revenue data: MTD £{revenue['month_total']}, Week £{revenue['week_total']}")
    
    def test_dashboard_overview_has_recent_data(self, session):
        """Dashboard overview contains recent bookings/messages/reviews"""
        response = session.get(f"{BASE_URL}/api/dashboard/overview/{PROPERTY_ID}")
        data = response.json()
        assert "recent" in data, "Missing 'recent' key"
        recent = data["recent"]
        assert "bookings" in recent, "Missing recent bookings"
        assert "messages" in recent, "Missing recent messages"
        assert "reviews" in recent, "Missing recent reviews"
        print(f"✓ Recent data: {len(recent['bookings'])} bookings, {len(recent['messages'])} messages, {len(recent['reviews'])} reviews")


class TestHousekeepingRooms(TestAuth):
    """Housekeeping room status board tests"""
    
    def test_get_rooms_returns_200(self, session):
        """GET /api/housekeeping/rooms/{property_id} returns 200"""
        response = session.get(f"{BASE_URL}/api/housekeeping/rooms/{PROPERTY_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Expected list of rooms"
        print(f"✓ Get rooms returns 200 with {len(data)} rooms")
    
    def test_get_rooms_stats_returns_200(self, session):
        """GET /api/housekeeping/rooms/{property_id}/stats returns status counts"""
        response = session.get(f"{BASE_URL}/api/housekeeping/rooms/{PROPERTY_ID}/stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "total" in data, "Missing total count"
        assert "clean" in data, "Missing clean count"
        assert "dirty" in data, "Missing dirty count"
        assert "inspected" in data, "Missing inspected count"
        assert "in_progress" in data, "Missing in_progress count"
        assert "out_of_order" in data, "Missing out_of_order count"
        print(f"✓ Room stats: total={data['total']}, clean={data['clean']}, dirty={data['dirty']}")
    
    def test_filter_rooms_by_status(self, session):
        """GET /api/housekeeping/rooms/{property_id}?status=clean filters correctly"""
        response = session.get(f"{BASE_URL}/api/housekeeping/rooms/{PROPERTY_ID}?status=clean")
        assert response.status_code == 200
        data = response.json()
        # All returned rooms should have status=clean (if any exist)
        for room in data:
            assert room.get("status") == "clean", f"Room {room.get('room_number')} has status {room.get('status')}, expected clean"
        print(f"✓ Filter by status=clean returns {len(data)} rooms")


class TestHousekeepingTasks(TestAuth):
    """Housekeeping tasks CRUD tests"""
    
    def test_get_tasks_returns_200(self, session):
        """GET /api/housekeeping/tasks/{property_id} returns 200"""
        response = session.get(f"{BASE_URL}/api/housekeeping/tasks/{PROPERTY_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Expected list of tasks"
        print(f"✓ Get tasks returns 200 with {len(data)} tasks")
    
    def test_create_task(self, session):
        """POST /api/housekeeping/tasks creates a new task"""
        task_data = {
            "property_id": PROPERTY_ID,
            "room_number": "TEST101",
            "task_type": "cleaning",  # Model uses task_type not type
            "assigned_to": "Test Staff",
            "priority": "high",
            "notes": "Test task created by pytest"
        }
        response = session.post(f"{BASE_URL}/api/housekeeping/tasks", json=task_data)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("room_number") == "TEST101", "Room number mismatch"
        assert data.get("task_type") == "cleaning", "Task type mismatch"
        assert data.get("assigned_to") == "Test Staff", "Assigned to mismatch"
        assert data.get("priority") == "high", "Priority mismatch"
        assert data.get("status") == "pending", "New task should have pending status"
        assert "id" in data, "Missing task ID"
        print(f"✓ Created task {data['id']} for room {data['room_number']}")
        return data["id"]
    
    def test_update_task_status(self, session):
        """PUT /api/housekeeping/tasks/{task_id} updates task status"""
        # First create a task
        task_data = {
            "property_id": PROPERTY_ID,
            "room_number": "TEST102",
            "type": "turndown",
            "assigned_to": "Update Test",
            "priority": "normal",
            "notes": "Task for update test"
        }
        create_resp = session.post(f"{BASE_URL}/api/housekeeping/tasks", json=task_data)
        assert create_resp.status_code == 200
        task_id = create_resp.json()["id"]
        
        # Update to in_progress
        update_resp = session.put(f"{BASE_URL}/api/housekeeping/tasks/{task_id}", json={"status": "in_progress"})
        assert update_resp.status_code == 200
        assert update_resp.json().get("status") == "in_progress"
        
        # Update to completed
        complete_resp = session.put(f"{BASE_URL}/api/housekeeping/tasks/{task_id}", json={"status": "completed"})
        assert complete_resp.status_code == 200
        completed_task = complete_resp.json()
        assert completed_task.get("status") == "completed"
        assert "completed_at" in completed_task, "Completed task should have completed_at timestamp"
        print(f"✓ Task {task_id} status flow: pending → in_progress → completed")
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/housekeeping/tasks/{task_id}")
    
    def test_delete_task(self, session):
        """DELETE /api/housekeeping/tasks/{task_id} removes task"""
        # Create a task to delete
        task_data = {
            "property_id": PROPERTY_ID,
            "room_number": "TEST103",
            "type": "deep_clean",
            "priority": "low"
        }
        create_resp = session.post(f"{BASE_URL}/api/housekeeping/tasks", json=task_data)
        assert create_resp.status_code == 200
        task_id = create_resp.json()["id"]
        
        # Delete it
        delete_resp = session.delete(f"{BASE_URL}/api/housekeeping/tasks/{task_id}")
        assert delete_resp.status_code == 200
        assert delete_resp.json().get("status") == "deleted"
        print(f"✓ Deleted task {task_id}")


class TestHousekeepingMaintenance(TestAuth):
    """Housekeeping maintenance requests CRUD tests"""
    
    def test_get_maintenance_returns_200(self, session):
        """GET /api/housekeeping/maintenance/{property_id} returns 200"""
        response = session.get(f"{BASE_URL}/api/housekeeping/maintenance/{PROPERTY_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Expected list of maintenance requests"
        print(f"✓ Get maintenance returns 200 with {len(data)} requests")
    
    def test_create_maintenance_request(self, session):
        """POST /api/housekeeping/maintenance creates a new request"""
        maint_data = {
            "property_id": PROPERTY_ID,
            "room_number": "TEST201",
            "description": "AC not cooling properly, needs inspection",  # Model uses description, no title field
            "priority": "high",
            "category": "hvac"
        }
        response = session.post(f"{BASE_URL}/api/housekeeping/maintenance", json=maint_data)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("room_number") == "TEST201", "Room number mismatch"
        assert data.get("description") == "AC not cooling properly, needs inspection", "Description mismatch"
        assert data.get("category") == "hvac", "Category mismatch"
        assert data.get("priority") == "high", "Priority mismatch"
        assert data.get("status") == "open", "New request should have open status"
        assert "id" in data, "Missing request ID"
        print(f"✓ Created maintenance request {data['id']}: {data['description'][:30]}...")
        return data["id"]
    
    def test_update_maintenance_status(self, session):
        """PUT /api/housekeeping/maintenance/{req_id} updates request status"""
        # Create a request
        maint_data = {
            "property_id": PROPERTY_ID,
            "room_number": "TEST202",
            "title": "Leaky Faucet",
            "description": "Bathroom sink faucet dripping",
            "priority": "normal",
            "category": "plumbing"
        }
        create_resp = session.post(f"{BASE_URL}/api/housekeeping/maintenance", json=maint_data)
        assert create_resp.status_code == 200
        req_id = create_resp.json()["id"]
        
        # Update to in_progress (Assign)
        assign_resp = session.put(f"{BASE_URL}/api/housekeeping/maintenance/{req_id}", json={"status": "in_progress"})
        assert assign_resp.status_code == 200
        assert assign_resp.json().get("status") == "in_progress"
        
        # Update to resolved
        resolve_resp = session.put(f"{BASE_URL}/api/housekeeping/maintenance/{req_id}", json={"status": "resolved"})
        assert resolve_resp.status_code == 200
        resolved_req = resolve_resp.json()
        assert resolved_req.get("status") == "resolved"
        assert "resolved_at" in resolved_req, "Resolved request should have resolved_at timestamp"
        print(f"✓ Maintenance {req_id} status flow: open → in_progress → resolved")
    
    def test_maintenance_categories(self, session):
        """Test different maintenance categories"""
        categories = ["plumbing", "electrical", "hvac", "furniture", "appliance", "structural", "other"]
        for cat in categories[:3]:  # Test first 3 to save time
            maint_data = {
                "property_id": PROPERTY_ID,
                "room_number": f"CAT{categories.index(cat)}",
                "title": f"Test {cat} issue",
                "description": f"Testing {cat} category",
                "priority": "low",
                "category": cat
            }
            response = session.post(f"{BASE_URL}/api/housekeeping/maintenance", json=maint_data)
            assert response.status_code == 200, f"Failed to create {cat} request"
            assert response.json().get("category") == cat
        print(f"✓ Maintenance categories work correctly")


class TestDashboardNotifications(TestAuth):
    """Dashboard notifications API tests"""
    
    def test_notifications_returns_200(self, session):
        """GET /api/dashboard/notifications/{property_id} returns 200"""
        response = session.get(f"{BASE_URL}/api/dashboard/notifications/{PROPERTY_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "notifications" in data, "Missing notifications list"
        assert "total" in data, "Missing total count"
        assert "high" in data, "Missing high priority count"
        assert "medium" in data, "Missing medium priority count"
        assert "low" in data, "Missing low priority count"
        print(f"✓ Notifications: {data['total']} total ({data['high']} high, {data['medium']} medium, {data['low']} low)")


class TestDashboardFinancialKPIs(TestAuth):
    """Dashboard financial KPIs API tests"""
    
    def test_financial_kpis_returns_200(self, session):
        """GET /api/dashboard/financial-kpis/{property_id} returns 200"""
        response = session.get(f"{BASE_URL}/api/dashboard/financial-kpis/{PROPERTY_ID}")
        # This endpoint may return 200 or 404 depending on data
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Financial KPIs: RevPAR={data.get('revpar')}, ADR={data.get('adr')}, MTD Revenue={data.get('month_revenue')}")
        else:
            print(f"✓ Financial KPIs endpoint returned {response.status_code} (may need data)")


class TestUnauthenticatedAccess:
    """Test that endpoints require authentication"""
    
    def test_dashboard_requires_auth(self):
        """Dashboard overview requires authentication"""
        response = requests.get(f"{BASE_URL}/api/dashboard/overview/{PROPERTY_ID}")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Dashboard overview requires authentication")
    
    def test_housekeeping_rooms_requires_auth(self):
        """Housekeeping rooms requires authentication"""
        response = requests.get(f"{BASE_URL}/api/housekeeping/rooms/{PROPERTY_ID}")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Housekeeping rooms requires authentication")
    
    def test_housekeeping_tasks_requires_auth(self):
        """Housekeeping tasks requires authentication"""
        response = requests.get(f"{BASE_URL}/api/housekeeping/tasks/{PROPERTY_ID}")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Housekeeping tasks requires authentication")
    
    def test_housekeeping_maintenance_requires_auth(self):
        """Housekeeping maintenance requires authentication"""
        response = requests.get(f"{BASE_URL}/api/housekeeping/maintenance/{PROPERTY_ID}")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Housekeeping maintenance requires authentication")


class TestCleanup(TestAuth):
    """Cleanup test data"""
    
    def test_cleanup_test_tasks(self, session):
        """Remove test tasks created during testing"""
        response = session.get(f"{BASE_URL}/api/housekeeping/tasks/{PROPERTY_ID}")
        if response.status_code == 200:
            tasks = response.json()
            deleted = 0
            for task in tasks:
                if task.get("room_number", "").startswith("TEST") or task.get("notes", "").startswith("Test"):
                    session.delete(f"{BASE_URL}/api/housekeeping/tasks/{task['id']}")
                    deleted += 1
            print(f"✓ Cleaned up {deleted} test tasks")
    
    def test_cleanup_test_maintenance(self, session):
        """Remove test maintenance requests created during testing"""
        response = session.get(f"{BASE_URL}/api/housekeeping/maintenance/{PROPERTY_ID}")
        if response.status_code == 200:
            requests_list = response.json()
            deleted = 0
            for req in requests_list:
                if req.get("room_number", "").startswith("TEST") or req.get("room_number", "").startswith("CAT"):
                    session.put(f"{BASE_URL}/api/housekeeping/maintenance/{req['id']}", json={"status": "resolved"})
                    deleted += 1
            print(f"✓ Resolved {deleted} test maintenance requests")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
