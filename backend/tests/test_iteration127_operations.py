"""
Iteration 127 - Operations Features Testing
Tests for: Shift Scheduler, Reception Report, Pass Over Duties
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
STAFF_EMAIL = "ali@hotel.com"
STAFF_PASSWORD = "Staff2026!"


class TestAuth:
    """Authentication helper tests"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip(f"Admin auth failed: {response.status_code} - {response.text}")
    
    @pytest.fixture(scope="class")
    def staff_token(self):
        """Get staff authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": STAFF_EMAIL,
            "password": STAFF_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("token")
        return None  # Staff may not exist
    
    def test_admin_login(self):
        """Test admin login works"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        print(f"Admin login successful, token received")


class TestShiftScheduler:
    """Shift Scheduler endpoint tests"""
    
    @pytest.fixture(scope="class")
    def admin_headers(self):
        """Get admin auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json().get("token")
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_shifts_returns_structure(self, admin_headers):
        """GET /api/operations/shifts/all returns correct structure"""
        # Get current week start (Monday)
        today = datetime.now()
        week_start = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")
        
        response = requests.get(
            f"{BASE_URL}/api/operations/shifts/all?week_start={week_start}",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert "week_start" in data
        assert "week_end" in data
        assert "days" in data
        assert "staff" in data
        assert "total_staff" in data
        
        # Verify days array has 7 days
        assert len(data["days"]) == 7
        
        # Verify each day has required fields
        for day in data["days"]:
            assert "date" in day
            assert "dow" in day
            assert "day" in day
            assert "month" in day
        
        print(f"GET shifts: week_start={data['week_start']}, week_end={data['week_end']}, total_staff={data['total_staff']}, days={len(data['days'])}")
    
    def test_assign_shift_with_morning_preset(self, admin_headers):
        """POST /api/operations/shifts/all/assign with morning preset returns 07:00-15:00"""
        today = datetime.now()
        test_date = today.strftime("%Y-%m-%d")
        
        # First get staff list
        week_start = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")
        shifts_response = requests.get(
            f"{BASE_URL}/api/operations/shifts/all?week_start={week_start}",
            headers=admin_headers
        )
        staff_list = shifts_response.json().get("staff", [])
        
        if not staff_list:
            pytest.skip("No staff available for shift assignment")
        
        staff_id = staff_list[0]["id"]
        
        response = requests.post(
            f"{BASE_URL}/api/operations/shifts/all/assign",
            headers=admin_headers,
            json={
                "staff_id": staff_id,
                "date": test_date,
                "preset": "morning"
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify morning preset times
        assert data["shift_start"] == "07:00", f"Expected 07:00, got {data['shift_start']}"
        assert data["shift_end"] == "15:00", f"Expected 15:00, got {data['shift_end']}"
        assert data["color"] == "#22c55e"
        assert data["status"] == "planned"
        assert "id" in data
        
        print(f"Shift assigned: {data['shift_start']}-{data['shift_end']} (morning preset), color={data['color']}")
    
    def test_assign_shift_with_afternoon_preset(self, admin_headers):
        """POST /api/operations/shifts/all/assign with afternoon preset returns 12:00-20:00"""
        today = datetime.now()
        test_date = (today + timedelta(days=1)).strftime("%Y-%m-%d")
        
        # Get staff
        week_start = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")
        shifts_response = requests.get(
            f"{BASE_URL}/api/operations/shifts/all?week_start={week_start}",
            headers=admin_headers
        )
        staff_list = shifts_response.json().get("staff", [])
        
        if not staff_list:
            pytest.skip("No staff available")
        
        staff_id = staff_list[0]["id"]
        
        response = requests.post(
            f"{BASE_URL}/api/operations/shifts/all/assign",
            headers=admin_headers,
            json={
                "staff_id": staff_id,
                "date": test_date,
                "preset": "afternoon"
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["shift_start"] == "12:00"
        assert data["shift_end"] == "20:00"
        assert data["color"] == "#06b6d4"
        print(f"Afternoon shift: {data['shift_start']}-{data['shift_end']}")
    
    def test_bulk_publish_shifts(self, admin_headers):
        """POST /api/operations/shifts/all/bulk-publish updates statuses"""
        today = datetime.now()
        week_start = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")
        
        response = requests.post(
            f"{BASE_URL}/api/operations/shifts/all/bulk-publish",
            headers=admin_headers,
            json={
                "week_start": week_start,
                "action": "publish"
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "updated" in data
        assert "status" in data
        assert data["status"] == "published"
        
        print(f"Bulk publish: {data['updated']} shifts updated to {data['status']}")
    
    def test_bulk_approve_shifts(self, admin_headers):
        """POST /api/operations/shifts/all/bulk-publish with approve action"""
        today = datetime.now()
        week_start = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")
        
        response = requests.post(
            f"{BASE_URL}/api/operations/shifts/all/bulk-publish",
            headers=admin_headers,
            json={
                "week_start": week_start,
                "action": "approve"
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "approved"
        print(f"Bulk approve: {data['updated']} shifts approved")
    
    def test_clear_week_shifts(self, admin_headers):
        """DELETE /api/operations/shifts/all/clear-week clears shifts"""
        # Use a test week in the past to avoid affecting current data
        test_week = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        response = requests.delete(
            f"{BASE_URL}/api/operations/shifts/all/clear-week?week_start={test_week}",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "deleted" in data
        print(f"Clear week: {data['deleted']} shifts deleted for week {test_week}")
    
    def test_shifts_unauthorized(self):
        """Shifts endpoints require authentication"""
        response = requests.get(f"{BASE_URL}/api/operations/shifts/all")
        assert response.status_code == 401
        print("Shifts endpoint correctly returns 401 without auth")


class TestReceptionReport:
    """Reception Report endpoint tests"""
    
    @pytest.fixture(scope="class")
    def admin_headers(self):
        """Get admin auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json().get("token")
        return {"Authorization": f"Bearer {token}"}
    
    def test_reception_report_returns_kpis(self, admin_headers):
        """GET /api/operations/reception-report/all returns KPIs and detail arrays"""
        today = datetime.now()
        start = (today - timedelta(days=7)).strftime("%Y-%m-%d")
        end = today.strftime("%Y-%m-%d")
        
        response = requests.get(
            f"{BASE_URL}/api/operations/reception-report/all?start={start}&end={end}",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert "period" in data
        assert "kpis" in data
        assert "bookings_created" in data
        assert "check_ins" in data
        assert "check_outs" in data
        assert "cancellations" in data
        assert "routine_runs" in data
        
        # Verify KPIs
        kpis = data["kpis"]
        assert "bookings_created" in kpis
        assert "check_ins" in kpis
        assert "check_outs" in kpis
        assert "cancellations" in kpis
        assert "routine_runs" in kpis
        
        print(f"Reception Report KPIs: bookings={kpis['bookings_created']}, check_ins={kpis['check_ins']}, check_outs={kpis['check_outs']}, cancellations={kpis['cancellations']}, routines={kpis['routine_runs']}")
    
    def test_reception_report_unauthorized(self):
        """Reception report requires authentication"""
        response = requests.get(f"{BASE_URL}/api/operations/reception-report/all")
        assert response.status_code == 401
        print("Reception report correctly returns 401 without auth")


class TestPassOverDuties:
    """Pass Over Duties endpoint tests"""
    
    @pytest.fixture(scope="class")
    def admin_headers(self):
        """Get admin auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json().get("token")
        return {"Authorization": f"Bearer {token}"}
    
    def test_list_pass_overs_returns_structure(self, admin_headers):
        """GET /api/operations/pass-over/all returns items, counts, total"""
        response = requests.get(
            f"{BASE_URL}/api/operations/pass-over/all",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "items" in data
        assert "counts" in data
        assert "total" in data
        assert isinstance(data["items"], list)
        
        print(f"Pass-over list: total={data['total']}, counts={data['counts']}")
    
    def test_list_pass_overs_with_status_filter(self, admin_headers):
        """GET /api/operations/pass-over/all?status=open filters correctly"""
        response = requests.get(
            f"{BASE_URL}/api/operations/pass-over/all?status=open",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # All items should have status=open
        for item in data["items"]:
            assert item["status"] == "open", f"Expected status=open, got {item['status']}"
        
        print(f"Filtered by status=open: {len(data['items'])} items")
    
    def test_list_pass_overs_with_priority_filter(self, admin_headers):
        """GET /api/operations/pass-over/all?priority=critical filters correctly"""
        response = requests.get(
            f"{BASE_URL}/api/operations/pass-over/all?priority=critical",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # All items should have priority=critical
        for item in data["items"]:
            assert item["priority"] == "critical", f"Expected priority=critical, got {item['priority']}"
        
        print(f"Filtered by priority=critical: {len(data['items'])} items")
    
    def test_create_pass_over_success(self, admin_headers):
        """POST /api/operations/pass-over/all creates pass-over with status=open"""
        response = requests.post(
            f"{BASE_URL}/api/operations/pass-over/all",
            headers=admin_headers,
            json={
                "title": "TEST_Room 204 boiler issue",
                "message": "Guest reported no hot water. Maintenance notified.",
                "priority": "high",
                "category": "maintenance",
                "shift": "morning",
                "mentions": ["Ali"]
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["title"] == "TEST_Room 204 boiler issue"
        assert data["message"] == "Guest reported no hot water. Maintenance notified."
        assert data["priority"] == "high"
        assert data["category"] == "maintenance"
        assert data["shift"] == "morning"
        assert data["status"] == "open"
        assert "id" in data
        assert "created_at" in data
        assert data["mentions"] == ["Ali"]
        
        print(f"Created pass-over: id={data['id']}, title={data['title']}, status={data['status']}")
        return data["id"]
    
    def test_create_pass_over_missing_title_returns_400(self, admin_headers):
        """POST /api/operations/pass-over/all returns 400 when title missing"""
        response = requests.post(
            f"{BASE_URL}/api/operations/pass-over/all",
            headers=admin_headers,
            json={
                "message": "Some message without title",
                "priority": "normal"
            }
        )
        assert response.status_code == 400
        print("Create pass-over without title correctly returns 400")
    
    def test_acknowledge_pass_over(self, admin_headers):
        """POST /api/operations/pass-over/all/{id}/acknowledge sets status=acknowledged"""
        # First create a pass-over
        create_response = requests.post(
            f"{BASE_URL}/api/operations/pass-over/all",
            headers=admin_headers,
            json={
                "title": "TEST_Acknowledge test",
                "message": "Testing acknowledge flow",
                "priority": "normal"
            }
        )
        item_id = create_response.json()["id"]
        
        # Acknowledge it
        response = requests.post(
            f"{BASE_URL}/api/operations/pass-over/all/{item_id}/acknowledge",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "acknowledged"
        assert len(data["acknowledgements"]) > 0
        assert "user" in data["acknowledgements"][0]
        assert "at" in data["acknowledgements"][0]
        
        print(f"Acknowledged pass-over: id={item_id}, ack_count={len(data['acknowledgements'])}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/operations/pass-over/all/{item_id}", headers=admin_headers)
    
    def test_archive_pass_over(self, admin_headers):
        """POST /api/operations/pass-over/all/{id}/archive sets status=archived (admin/manager only)"""
        # First create a pass-over
        create_response = requests.post(
            f"{BASE_URL}/api/operations/pass-over/all",
            headers=admin_headers,
            json={
                "title": "TEST_Archive test",
                "message": "Testing archive flow",
                "priority": "low"
            }
        )
        item_id = create_response.json()["id"]
        
        # Archive it
        response = requests.post(
            f"{BASE_URL}/api/operations/pass-over/all/{item_id}/archive",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["archived"] == True
        
        # Verify it's archived
        get_response = requests.get(
            f"{BASE_URL}/api/operations/pass-over/all?status=archived",
            headers=admin_headers
        )
        archived_items = [i for i in get_response.json()["items"] if i["id"] == item_id]
        assert len(archived_items) == 1
        assert archived_items[0]["status"] == "archived"
        
        print(f"Archived pass-over: id={item_id}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/operations/pass-over/all/{item_id}", headers=admin_headers)
    
    def test_delete_pass_over(self, admin_headers):
        """DELETE /api/operations/pass-over/all/{id} removes it (admin/manager only)"""
        # First create a pass-over
        create_response = requests.post(
            f"{BASE_URL}/api/operations/pass-over/all",
            headers=admin_headers,
            json={
                "title": "TEST_Delete test",
                "message": "Testing delete flow",
                "priority": "normal"
            }
        )
        item_id = create_response.json()["id"]
        
        # Delete it
        response = requests.delete(
            f"{BASE_URL}/api/operations/pass-over/all/{item_id}",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["deleted"] == True
        
        # Verify it's gone
        get_response = requests.get(
            f"{BASE_URL}/api/operations/pass-over/all?status=all",
            headers=admin_headers
        )
        deleted_items = [i for i in get_response.json()["items"] if i["id"] == item_id]
        assert len(deleted_items) == 0
        
        print(f"Deleted pass-over: id={item_id}")
    
    def test_delete_unknown_id_returns_404(self, admin_headers):
        """DELETE /api/operations/pass-over/all/{id} returns 404 for unknown id"""
        response = requests.delete(
            f"{BASE_URL}/api/operations/pass-over/all/nonexistent-id-12345",
            headers=admin_headers
        )
        assert response.status_code == 404
        print("Delete unknown pass-over correctly returns 404")
    
    def test_pass_over_unauthorized(self):
        """Pass-over endpoints require authentication"""
        response = requests.get(f"{BASE_URL}/api/operations/pass-over/all")
        assert response.status_code == 401
        print("Pass-over endpoint correctly returns 401 without auth")


class TestCleanup:
    """Cleanup test data"""
    
    @pytest.fixture(scope="class")
    def admin_headers(self):
        """Get admin auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json().get("token")
        return {"Authorization": f"Bearer {token}"}
    
    def test_cleanup_test_pass_overs(self, admin_headers):
        """Clean up TEST_ prefixed pass-overs"""
        response = requests.get(
            f"{BASE_URL}/api/operations/pass-over/all?status=all",
            headers=admin_headers
        )
        items = response.json().get("items", [])
        
        deleted = 0
        for item in items:
            if item.get("title", "").startswith("TEST_"):
                requests.delete(
                    f"{BASE_URL}/api/operations/pass-over/all/{item['id']}",
                    headers=admin_headers
                )
                deleted += 1
        
        print(f"Cleanup: deleted {deleted} TEST_ pass-overs")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
