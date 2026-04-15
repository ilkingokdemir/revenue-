"""
Iteration 82 - Operations Hub Backend Tests
Tests for:
1. Reception Dashboard - GET /api/operations/reception/{property_id}
2. Routine Templates - CRUD /api/operations/routine-templates
3. Routine History - GET/PUT /api/operations/routine-history
4. Pass Over Duties (Shift Handover) - CRUD /api/operations/handover
5. Laundry Management - CRUD /api/operations/laundry
6. Compliance Checks - CRUD /api/operations/compliance
7. Shift Scheduler - CRUD /api/shifts/staff, /api/shifts/entries, bulk actions
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
TEST_PROPERTY = "aldgate-flats"

class TestAuth:
    """Authentication tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, f"Token not in response: {data}"
        return data["token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Get auth headers"""
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestReceptionDashboard(TestAuth):
    """Reception Dashboard API tests"""
    
    def test_reception_dashboard_get(self, auth_headers):
        """GET /api/operations/reception/{property_id} - returns KPI stats"""
        response = requests.get(f"{BASE_URL}/api/operations/reception/{TEST_PROPERTY}", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify structure
        assert "stats" in data
        assert "from_date" in data
        assert "to_date" in data
        assert "bookings" in data
        assert "checkins" in data
        assert "checkouts" in data
        
        # Verify stats fields
        stats = data["stats"]
        assert "bookings_created" in stats
        assert "check_ins" in stats
        assert "check_outs" in stats
        assert "cancellations" in stats
        assert "routine_runs" in stats
        print(f"Reception stats: {stats}")
    
    def test_reception_dashboard_with_date_filter(self, auth_headers):
        """GET /api/operations/reception/{property_id}?from_date=&to_date= - date filtering"""
        response = requests.get(
            f"{BASE_URL}/api/operations/reception/{TEST_PROPERTY}?from_date=2025-01-01&to_date=2025-12-31",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["from_date"] == "2025-01-01"
        assert data["to_date"] == "2025-12-31"
    
    def test_reception_dashboard_all_properties(self, auth_headers):
        """GET /api/operations/reception/all - works with 'all' property_id"""
        response = requests.get(f"{BASE_URL}/api/operations/reception/all", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "stats" in data
    
    def test_reception_dashboard_requires_auth(self):
        """GET /api/operations/reception/{property_id} - requires authentication"""
        response = requests.get(f"{BASE_URL}/api/operations/reception/{TEST_PROPERTY}")
        assert response.status_code == 401


class TestRoutineTemplates(TestAuth):
    """Routine Templates CRUD tests"""
    
    @pytest.fixture
    def test_template_id(self, auth_headers):
        """Create a test template and return its ID"""
        payload = {
            "name": f"TEST_Template_{uuid.uuid4().hex[:8]}",
            "description": "Test routine template",
            "steps": ["Step 1: Check emails", "Step 2: Review bookings", "Step 3: Update status"],
            "role": "receptionist",
            "shift": "morning",
            "property_id": TEST_PROPERTY
        }
        response = requests.post(f"{BASE_URL}/api/operations/routine-templates", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Create failed: {response.text}"
        data = response.json()
        yield data["id"]
        # Cleanup
        requests.delete(f"{BASE_URL}/api/operations/routine-templates/{data['id']}", headers=auth_headers)
    
    def test_create_routine_template(self, auth_headers):
        """POST /api/operations/routine-templates - create template"""
        payload = {
            "name": f"TEST_Morning_Routine_{uuid.uuid4().hex[:8]}",
            "description": "Morning receptionist routine",
            "steps": ["Check overnight emails", "Review arrivals", "Prepare welcome packs"],
            "role": "receptionist",
            "shift": "morning",
            "property_id": TEST_PROPERTY
        }
        response = requests.post(f"{BASE_URL}/api/operations/routine-templates", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "id" in data
        assert data["name"] == payload["name"]
        assert data["steps"] == payload["steps"]
        assert data["role"] == "receptionist"
        assert data["shift"] == "morning"
        assert data["is_active"] == True
        assert "created_at" in data
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/operations/routine-templates/{data['id']}", headers=auth_headers)
        print(f"Created template: {data['id']}")
    
    def test_list_routine_templates(self, auth_headers, test_template_id):
        """GET /api/operations/routine-templates/{property_id} - list templates"""
        response = requests.get(f"{BASE_URL}/api/operations/routine-templates/{TEST_PROPERTY}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should contain our test template
        template_ids = [t["id"] for t in data]
        assert test_template_id in template_ids
    
    def test_update_routine_template(self, auth_headers, test_template_id):
        """PUT /api/operations/routine-templates/{template_id} - update template"""
        updates = {
            "name": "TEST_Updated_Template",
            "description": "Updated description",
            "steps": ["New Step 1", "New Step 2"]
        }
        response = requests.put(
            f"{BASE_URL}/api/operations/routine-templates/{test_template_id}",
            json=updates, headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["name"] == "TEST_Updated_Template"
        assert data["description"] == "Updated description"
        assert data["steps"] == ["New Step 1", "New Step 2"]
    
    def test_delete_routine_template(self, auth_headers):
        """DELETE /api/operations/routine-templates/{template_id} - delete template"""
        # Create a template to delete
        payload = {"name": f"TEST_ToDelete_{uuid.uuid4().hex[:8]}", "steps": ["Step 1"], "property_id": TEST_PROPERTY}
        create_resp = requests.post(f"{BASE_URL}/api/operations/routine-templates", json=payload, headers=auth_headers)
        template_id = create_resp.json()["id"]
        
        # Delete it
        response = requests.delete(f"{BASE_URL}/api/operations/routine-templates/{template_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["status"] == "deleted"
        
        # Verify it's gone
        list_resp = requests.get(f"{BASE_URL}/api/operations/routine-templates/{TEST_PROPERTY}", headers=auth_headers)
        template_ids = [t["id"] for t in list_resp.json()]
        assert template_id not in template_ids
    
    def test_start_routine_from_template(self, auth_headers, test_template_id):
        """POST /api/operations/routine-templates/{template_id}/start - start routine"""
        response = requests.post(
            f"{BASE_URL}/api/operations/routine-templates/{test_template_id}/start",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "id" in data
        assert data["template_id"] == test_template_id
        assert data["status"] == "in_progress"
        assert "tasks" in data
        assert len(data["tasks"]) > 0
        assert data["completed_tasks"] == 0
        assert "started_at" in data
        print(f"Started routine run: {data['id']}")


class TestRoutineHistory(TestAuth):
    """Routine History API tests"""
    
    @pytest.fixture
    def test_run_id(self, auth_headers):
        """Create a routine run for testing"""
        # First create a template
        template_payload = {
            "name": f"TEST_HistoryTemplate_{uuid.uuid4().hex[:8]}",
            "steps": ["Task 1", "Task 2", "Task 3"],
            "property_id": TEST_PROPERTY
        }
        template_resp = requests.post(f"{BASE_URL}/api/operations/routine-templates", json=template_payload, headers=auth_headers)
        template_id = template_resp.json()["id"]
        
        # Start a routine
        run_resp = requests.post(f"{BASE_URL}/api/operations/routine-templates/{template_id}/start", headers=auth_headers)
        run_id = run_resp.json()["id"]
        
        yield run_id
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/operations/routine-templates/{template_id}", headers=auth_headers)
    
    def test_list_routine_history(self, auth_headers, test_run_id):
        """GET /api/operations/routine-history/{property_id} - list history"""
        response = requests.get(f"{BASE_URL}/api/operations/routine-history/{TEST_PROPERTY}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_routine_history_filter_by_status(self, auth_headers, test_run_id):
        """GET /api/operations/routine-history/{property_id}?status=in_progress - filter by status"""
        response = requests.get(
            f"{BASE_URL}/api/operations/routine-history/{TEST_PROPERTY}?status=in_progress",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        for run in data:
            assert run["status"] == "in_progress"
    
    def test_routine_history_stats(self, auth_headers):
        """GET /api/operations/routine-history/stats/{property_id} - get stats"""
        response = requests.get(f"{BASE_URL}/api/operations/routine-history/stats/{TEST_PROPERTY}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "total" in data
        assert "completed" in data
        assert "incomplete" in data
        assert "completion_rate" in data
        print(f"Routine stats: {data}")
    
    def test_complete_task_in_routine(self, auth_headers, test_run_id):
        """PUT /api/operations/routine-history/{run_id}/task/{task_index} - complete task"""
        response = requests.put(
            f"{BASE_URL}/api/operations/routine-history/{test_run_id}/task/0",
            json={"completed": True, "notes": "Task completed successfully"},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert data["tasks"][0]["completed"] == True
        assert data["completed_tasks"] == 1
        print(f"Completed task 0 in run {test_run_id}")


class TestPassOverDuties(TestAuth):
    """Pass Over Duties (Shift Handover) CRUD tests"""
    
    @pytest.fixture
    def test_note_id(self, auth_headers):
        """Create a test handover note"""
        payload = {
            "content": f"TEST_Note_{uuid.uuid4().hex[:8]}: Guest in room 302 requested late checkout",
            "note_type": "guest",
            "priority": "high",
            "owner": "Night Shift",
            "role_target": "receptionist",
            "property_id": TEST_PROPERTY
        }
        response = requests.post(f"{BASE_URL}/api/operations/handover", json=payload, headers=auth_headers)
        data = response.json()
        yield data["id"]
        # Cleanup
        requests.delete(f"{BASE_URL}/api/operations/handover/{data['id']}", headers=auth_headers)
    
    def test_create_handover_note(self, auth_headers):
        """POST /api/operations/handover - create note"""
        payload = {
            "content": f"TEST_Handover_{uuid.uuid4().hex[:8]}: VIP guest arriving tomorrow",
            "note_type": "urgent",
            "priority": "critical",
            "owner": "Manager",
            "role_target": "receptionist",
            "property_id": TEST_PROPERTY
        }
        response = requests.post(f"{BASE_URL}/api/operations/handover", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "id" in data
        assert data["note_type"] == "urgent"
        assert data["priority"] == "critical"
        assert data["status"] == "pending"
        assert "author" in data
        assert "created_at" in data
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/operations/handover/{data['id']}", headers=auth_headers)
        print(f"Created handover note: {data['id']}")
    
    def test_list_handover_notes(self, auth_headers, test_note_id):
        """GET /api/operations/handover/{property_id} - list notes"""
        response = requests.get(f"{BASE_URL}/api/operations/handover/{TEST_PROPERTY}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_filter_handover_by_type(self, auth_headers, test_note_id):
        """GET /api/operations/handover/{property_id}?note_type=guest - filter by type"""
        response = requests.get(
            f"{BASE_URL}/api/operations/handover/{TEST_PROPERTY}?note_type=guest",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        for note in data:
            assert note["note_type"] == "guest"
    
    def test_filter_handover_by_priority(self, auth_headers, test_note_id):
        """GET /api/operations/handover/{property_id}?priority=high - filter by priority"""
        response = requests.get(
            f"{BASE_URL}/api/operations/handover/{TEST_PROPERTY}?priority=high",
            headers=auth_headers
        )
        assert response.status_code == 200
    
    def test_resolve_handover_note(self, auth_headers, test_note_id):
        """PUT /api/operations/handover/{note_id} - resolve note"""
        response = requests.put(
            f"{BASE_URL}/api/operations/handover/{test_note_id}",
            json={"status": "resolved"},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert data["status"] == "resolved"
        assert "resolved_by" in data
        assert "resolved_at" in data
        print(f"Resolved note: {test_note_id}")
    
    def test_delete_handover_note(self, auth_headers):
        """DELETE /api/operations/handover/{note_id} - delete note"""
        # Create a note to delete
        payload = {"content": f"TEST_ToDelete_{uuid.uuid4().hex[:8]}", "property_id": TEST_PROPERTY}
        create_resp = requests.post(f"{BASE_URL}/api/operations/handover", json=payload, headers=auth_headers)
        note_id = create_resp.json()["id"]
        
        # Delete it
        response = requests.delete(f"{BASE_URL}/api/operations/handover/{note_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["status"] == "deleted"


class TestLaundryManagement(TestAuth):
    """Laundry Management CRUD tests"""
    
    @pytest.fixture
    def test_laundry_id(self, auth_headers):
        """Create a test laundry item"""
        payload = {
            "room_number": "TEST_302",
            "guest_name": "Test Guest",
            "items": ["Towels", "Sheets", "Pillowcases"],
            "total_pieces": 10,
            "notes": "Express service requested",
            "property_id": TEST_PROPERTY
        }
        response = requests.post(f"{BASE_URL}/api/operations/laundry", json=payload, headers=auth_headers)
        data = response.json()
        yield data["id"]
        # No cleanup needed - laundry items persist
    
    def test_create_laundry_dispatch(self, auth_headers):
        """POST /api/operations/laundry - dispatch laundry"""
        payload = {
            "room_number": f"TEST_{uuid.uuid4().hex[:4]}",
            "guest_name": "John Smith",
            "items": ["Towels", "Bathrobes"],
            "total_pieces": 5,
            "notes": "Handle with care",
            "property_id": TEST_PROPERTY
        }
        response = requests.post(f"{BASE_URL}/api/operations/laundry", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "id" in data
        assert data["status"] == "sent"
        assert data["room_number"] == payload["room_number"]
        assert data["total_pieces"] == 5
        assert "sent_by" in data
        assert "sent_at" in data
        print(f"Created laundry dispatch: {data['id']}")
    
    def test_list_laundry_items(self, auth_headers, test_laundry_id):
        """GET /api/operations/laundry/{property_id} - list items"""
        response = requests.get(f"{BASE_URL}/api/operations/laundry/{TEST_PROPERTY}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_filter_laundry_by_status(self, auth_headers, test_laundry_id):
        """GET /api/operations/laundry/{property_id}?status=sent - filter by status"""
        response = requests.get(
            f"{BASE_URL}/api/operations/laundry/{TEST_PROPERTY}?status=sent",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        for item in data:
            assert item["status"] == "sent"
    
    def test_update_laundry_status_to_in_progress(self, auth_headers, test_laundry_id):
        """PUT /api/operations/laundry/{item_id} - update to in_progress"""
        response = requests.put(
            f"{BASE_URL}/api/operations/laundry/{test_laundry_id}",
            json={"status": "in_progress"},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["status"] == "in_progress"
    
    def test_update_laundry_status_to_returned(self, auth_headers, test_laundry_id):
        """PUT /api/operations/laundry/{item_id} - update to returned"""
        response = requests.put(
            f"{BASE_URL}/api/operations/laundry/{test_laundry_id}",
            json={"status": "returned"},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["status"] == "returned"
        assert "returned_at" in data
        assert "returned_by" in data
    
    def test_laundry_stats(self, auth_headers):
        """GET /api/operations/laundry/stats/{property_id} - get stats"""
        response = requests.get(f"{BASE_URL}/api/operations/laundry/stats/{TEST_PROPERTY}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "total" in data
        assert "sent" in data
        assert "in_progress" in data
        assert "returned" in data
        assert "total_pieces" in data
        print(f"Laundry stats: {data}")


class TestComplianceChecks(TestAuth):
    """Compliance Checks CRUD tests"""
    
    @pytest.fixture
    def test_check_id(self, auth_headers):
        """Create a test compliance check"""
        payload = {
            "title": f"TEST_Fire_Safety_{uuid.uuid4().hex[:8]}",
            "description": "Monthly fire safety inspection",
            "check_type": "fire",
            "frequency": "monthly",
            "scheduled_date": "2026-02-01",
            "inspector": "Safety Officer",
            "checklist_items": ["Fire extinguishers checked", "Emergency exits clear", "Smoke detectors working"],
            "property_id": TEST_PROPERTY
        }
        response = requests.post(f"{BASE_URL}/api/operations/compliance", json=payload, headers=auth_headers)
        data = response.json()
        yield data["id"]
        # Cleanup
        requests.delete(f"{BASE_URL}/api/operations/compliance/{data['id']}", headers=auth_headers)
    
    def test_create_compliance_check(self, auth_headers):
        """POST /api/operations/compliance - create check"""
        payload = {
            "title": f"TEST_Health_Inspection_{uuid.uuid4().hex[:8]}",
            "description": "Quarterly health inspection",
            "check_type": "health",
            "frequency": "quarterly",
            "scheduled_date": "2026-03-15",
            "inspector": "Health Inspector",
            "checklist_items": ["Kitchen hygiene", "Food storage", "Staff health certificates"],
            "property_id": TEST_PROPERTY
        }
        response = requests.post(f"{BASE_URL}/api/operations/compliance", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "id" in data
        assert data["check_type"] == "health"
        assert data["status"] == "scheduled"
        assert data["frequency"] == "quarterly"
        assert len(data["checklist"]) == 3
        assert "created_by" in data
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/operations/compliance/{data['id']}", headers=auth_headers)
        print(f"Created compliance check: {data['id']}")
    
    def test_list_compliance_checks(self, auth_headers, test_check_id):
        """GET /api/operations/compliance/{property_id} - list checks"""
        response = requests.get(f"{BASE_URL}/api/operations/compliance/{TEST_PROPERTY}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_filter_compliance_by_type(self, auth_headers, test_check_id):
        """GET /api/operations/compliance/{property_id}?check_type=fire - filter by type"""
        response = requests.get(
            f"{BASE_URL}/api/operations/compliance/{TEST_PROPERTY}?check_type=fire",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        for check in data:
            assert check["check_type"] == "fire"
    
    def test_complete_compliance_check(self, auth_headers, test_check_id):
        """PUT /api/operations/compliance/{check_id} - complete check"""
        # Update checklist items to passed
        response = requests.put(
            f"{BASE_URL}/api/operations/compliance/{test_check_id}",
            json={
                "status": "completed",
                "checklist": [
                    {"item": "Fire extinguishers checked", "passed": True, "notes": "All OK"},
                    {"item": "Emergency exits clear", "passed": True, "notes": "Clear"},
                    {"item": "Smoke detectors working", "passed": True, "notes": "Tested"}
                ]
            },
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert data["status"] == "completed"
        assert data["result"] == "pass"
        assert "completed_at" in data
        assert "completed_by" in data
        print(f"Completed compliance check: {test_check_id}")
    
    def test_delete_compliance_check(self, auth_headers):
        """DELETE /api/operations/compliance/{check_id} - delete check"""
        # Create a check to delete
        payload = {"title": f"TEST_ToDelete_{uuid.uuid4().hex[:8]}", "check_type": "safety", "property_id": TEST_PROPERTY}
        create_resp = requests.post(f"{BASE_URL}/api/operations/compliance", json=payload, headers=auth_headers)
        check_id = create_resp.json()["id"]
        
        # Delete it
        response = requests.delete(f"{BASE_URL}/api/operations/compliance/{check_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["status"] == "deleted"


class TestShiftSchedulerStaff(TestAuth):
    """Shift Scheduler - Staff CRUD tests"""
    
    @pytest.fixture
    def test_staff_id(self, auth_headers):
        """Create a test staff member"""
        payload = {
            "name": f"TEST_Staff_{uuid.uuid4().hex[:8]}",
            "role": "housekeeper",
            "pay_type": "daily",
            "pay_rate": 80,
            "currency": "GBP",
            "email": f"test_{uuid.uuid4().hex[:8]}@hotel.com",
            "property_id": TEST_PROPERTY
        }
        response = requests.post(f"{BASE_URL}/api/shifts/staff", json=payload, headers=auth_headers)
        data = response.json()
        yield data["id"]
        # Cleanup
        requests.delete(f"{BASE_URL}/api/shifts/staff/{data['id']}", headers=auth_headers)
    
    def test_create_staff_member(self, auth_headers):
        """POST /api/shifts/staff - create staff"""
        payload = {
            "name": f"TEST_John_Doe_{uuid.uuid4().hex[:8]}",
            "role": "receptionist",
            "pay_type": "hourly",
            "pay_rate": 12.50,
            "currency": "GBP",
            "email": f"john_{uuid.uuid4().hex[:8]}@hotel.com",
            "phone": "+44123456789",
            "property_id": TEST_PROPERTY
        }
        response = requests.post(f"{BASE_URL}/api/shifts/staff", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "id" in data
        assert data["name"] == payload["name"]
        assert data["role"] == "receptionist"
        assert data["pay_type"] == "hourly"
        assert data["pay_rate"] == 12.50
        assert data["is_active"] == True
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/shifts/staff/{data['id']}", headers=auth_headers)
        print(f"Created staff: {data['id']}")
    
    def test_list_staff(self, auth_headers, test_staff_id):
        """GET /api/shifts/staff/{property_id} - list staff"""
        response = requests.get(f"{BASE_URL}/api/shifts/staff/{TEST_PROPERTY}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_filter_staff_by_role(self, auth_headers, test_staff_id):
        """GET /api/shifts/staff/{property_id}?role=housekeeper - filter by role"""
        response = requests.get(
            f"{BASE_URL}/api/shifts/staff/{TEST_PROPERTY}?role=housekeeper",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        for staff in data:
            assert staff["role"] == "housekeeper"
    
    def test_update_staff(self, auth_headers, test_staff_id):
        """PUT /api/shifts/staff/{staff_id} - update staff"""
        response = requests.put(
            f"{BASE_URL}/api/shifts/staff/{test_staff_id}",
            json={"pay_rate": 90, "role": "maintenance"},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["pay_rate"] == 90
        assert data["role"] == "maintenance"
    
    def test_delete_staff(self, auth_headers):
        """DELETE /api/shifts/staff/{staff_id} - delete staff"""
        # Create staff to delete
        payload = {"name": f"TEST_ToDelete_{uuid.uuid4().hex[:8]}", "property_id": TEST_PROPERTY}
        create_resp = requests.post(f"{BASE_URL}/api/shifts/staff", json=payload, headers=auth_headers)
        staff_id = create_resp.json()["id"]
        
        # Delete
        response = requests.delete(f"{BASE_URL}/api/shifts/staff/{staff_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["status"] == "deleted"


class TestShiftSchedulerEntries(TestAuth):
    """Shift Scheduler - Shift Entries CRUD tests"""
    
    @pytest.fixture
    def test_staff_for_shifts(self, auth_headers):
        """Create a staff member for shift tests"""
        payload = {
            "name": f"TEST_ShiftStaff_{uuid.uuid4().hex[:8]}",
            "role": "housekeeper",
            "pay_type": "daily",
            "pay_rate": 80,
            "property_id": TEST_PROPERTY
        }
        response = requests.post(f"{BASE_URL}/api/shifts/staff", json=payload, headers=auth_headers)
        data = response.json()
        yield data
        requests.delete(f"{BASE_URL}/api/shifts/staff/{data['id']}", headers=auth_headers)
    
    @pytest.fixture
    def test_shift_id(self, auth_headers, test_staff_for_shifts):
        """Create a test shift entry"""
        payload = {
            "staff_id": test_staff_for_shifts["id"],
            "staff_name": test_staff_for_shifts["name"],
            "role": test_staff_for_shifts["role"],
            "date": "2026-01-20",
            "week_start": "2026-01-20",
            "start_time": "09:00",
            "end_time": "17:00",
            "notes": "Regular shift",
            "pay_type": "daily",
            "pay_rate": 80,
            "property_id": TEST_PROPERTY
        }
        response = requests.post(f"{BASE_URL}/api/shifts/entries", json=payload, headers=auth_headers)
        data = response.json()
        yield data["id"]
        requests.delete(f"{BASE_URL}/api/shifts/entries/{data['id']}", headers=auth_headers)
    
    def test_create_shift_entry(self, auth_headers, test_staff_for_shifts):
        """POST /api/shifts/entries - create shift"""
        payload = {
            "staff_id": test_staff_for_shifts["id"],
            "staff_name": test_staff_for_shifts["name"],
            "role": test_staff_for_shifts["role"],
            "date": "2026-01-21",
            "week_start": "2026-01-20",
            "start_time": "08:00",
            "end_time": "16:00",
            "notes": "Morning shift",
            "pay_type": "daily",
            "pay_rate": 80,
            "property_id": TEST_PROPERTY
        }
        response = requests.post(f"{BASE_URL}/api/shifts/entries", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "id" in data
        assert data["staff_id"] == test_staff_for_shifts["id"]
        assert data["date"] == "2026-01-21"
        assert data["status"] == "planned"
        assert "created_by" in data
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/shifts/entries/{data['id']}", headers=auth_headers)
        print(f"Created shift: {data['id']}")
    
    def test_list_shift_entries(self, auth_headers, test_shift_id):
        """GET /api/shifts/entries/{property_id} - list shifts"""
        response = requests.get(f"{BASE_URL}/api/shifts/entries/{TEST_PROPERTY}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_filter_shifts_by_week(self, auth_headers, test_shift_id):
        """GET /api/shifts/entries/{property_id}?week_start=2026-01-20 - filter by week"""
        response = requests.get(
            f"{BASE_URL}/api/shifts/entries/{TEST_PROPERTY}?week_start=2026-01-20",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        for shift in data:
            assert shift["week_start"] == "2026-01-20"
    
    def test_update_shift_entry(self, auth_headers, test_shift_id):
        """PUT /api/shifts/entries/{shift_id} - update shift"""
        response = requests.put(
            f"{BASE_URL}/api/shifts/entries/{test_shift_id}",
            json={"status": "published", "notes": "Updated notes"},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["status"] == "published"
        assert data["notes"] == "Updated notes"
    
    def test_delete_shift_entry(self, auth_headers, test_staff_for_shifts):
        """DELETE /api/shifts/entries/{shift_id} - delete shift"""
        # Create shift to delete
        payload = {
            "staff_id": test_staff_for_shifts["id"],
            "staff_name": test_staff_for_shifts["name"],
            "date": "2026-01-22",
            "week_start": "2026-01-20",
            "property_id": TEST_PROPERTY
        }
        create_resp = requests.post(f"{BASE_URL}/api/shifts/entries", json=payload, headers=auth_headers)
        shift_id = create_resp.json()["id"]
        
        # Delete
        response = requests.delete(f"{BASE_URL}/api/shifts/entries/{shift_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["status"] == "deleted"


class TestShiftBulkActions(TestAuth):
    """Shift Scheduler - Bulk Actions tests"""
    
    @pytest.fixture
    def setup_bulk_test_data(self, auth_headers):
        """Create staff and shifts for bulk action tests"""
        # Create staff
        staff_payload = {
            "name": f"TEST_BulkStaff_{uuid.uuid4().hex[:8]}",
            "role": "housekeeper",
            "pay_type": "daily",
            "pay_rate": 80,
            "property_id": TEST_PROPERTY
        }
        staff_resp = requests.post(f"{BASE_URL}/api/shifts/staff", json=staff_payload, headers=auth_headers)
        staff = staff_resp.json()
        
        # Create multiple shifts for the week
        week_start = "2026-02-02"
        shift_ids = []
        for i in range(3):
            shift_payload = {
                "staff_id": staff["id"],
                "staff_name": staff["name"],
                "role": staff["role"],
                "date": f"2026-02-0{2+i}",
                "week_start": week_start,
                "start_time": "09:00",
                "end_time": "17:00",
                "status": "planned",
                "pay_type": "daily",
                "pay_rate": 80,
                "property_id": TEST_PROPERTY
            }
            shift_resp = requests.post(f"{BASE_URL}/api/shifts/entries", json=shift_payload, headers=auth_headers)
            shift_ids.append(shift_resp.json()["id"])
        
        yield {"staff_id": staff["id"], "shift_ids": shift_ids, "week_start": week_start}
        
        # Cleanup
        for sid in shift_ids:
            requests.delete(f"{BASE_URL}/api/shifts/entries/{sid}", headers=auth_headers)
        requests.delete(f"{BASE_URL}/api/shifts/staff/{staff['id']}", headers=auth_headers)
    
    def test_publish_all_shifts(self, auth_headers, setup_bulk_test_data):
        """POST /api/shifts/bulk/publish-all - publish all shifts"""
        response = requests.post(
            f"{BASE_URL}/api/shifts/bulk/publish-all",
            json={"week_start": setup_bulk_test_data["week_start"], "property_id": TEST_PROPERTY},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "published" in data
        print(f"Published {data['published']} shifts")
    
    def test_mark_completed_shifts(self, auth_headers, setup_bulk_test_data):
        """POST /api/shifts/bulk/mark-completed - mark all completed"""
        # First publish
        requests.post(
            f"{BASE_URL}/api/shifts/bulk/publish-all",
            json={"week_start": setup_bulk_test_data["week_start"], "property_id": TEST_PROPERTY},
            headers=auth_headers
        )
        
        # Then mark completed
        response = requests.post(
            f"{BASE_URL}/api/shifts/bulk/mark-completed",
            json={"week_start": setup_bulk_test_data["week_start"], "property_id": TEST_PROPERTY},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "completed" in data
        print(f"Marked {data['completed']} shifts as completed")
    
    def test_approve_completed_shifts(self, auth_headers, setup_bulk_test_data):
        """POST /api/shifts/bulk/approve-completed - approve completed shifts"""
        # First publish and mark completed
        requests.post(
            f"{BASE_URL}/api/shifts/bulk/publish-all",
            json={"week_start": setup_bulk_test_data["week_start"], "property_id": TEST_PROPERTY},
            headers=auth_headers
        )
        requests.post(
            f"{BASE_URL}/api/shifts/bulk/mark-completed",
            json={"week_start": setup_bulk_test_data["week_start"], "property_id": TEST_PROPERTY},
            headers=auth_headers
        )
        
        # Then approve
        response = requests.post(
            f"{BASE_URL}/api/shifts/bulk/approve-completed",
            json={"week_start": setup_bulk_test_data["week_start"], "property_id": TEST_PROPERTY},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "approved" in data
        print(f"Approved {data['approved']} shifts")
    
    def test_clear_week_shifts(self, auth_headers):
        """POST /api/shifts/bulk/clear-week - clear all shifts for week"""
        # Create a separate week to clear
        week_start = "2026-03-02"
        staff_payload = {"name": f"TEST_ClearStaff_{uuid.uuid4().hex[:8]}", "property_id": TEST_PROPERTY}
        staff_resp = requests.post(f"{BASE_URL}/api/shifts/staff", json=staff_payload, headers=auth_headers)
        staff = staff_resp.json()
        
        # Create shifts
        for i in range(2):
            shift_payload = {
                "staff_id": staff["id"],
                "staff_name": staff["name"],
                "date": f"2026-03-0{2+i}",
                "week_start": week_start,
                "property_id": TEST_PROPERTY
            }
            requests.post(f"{BASE_URL}/api/shifts/entries", json=shift_payload, headers=auth_headers)
        
        # Clear week
        response = requests.post(
            f"{BASE_URL}/api/shifts/bulk/clear-week",
            json={"week_start": week_start, "property_id": TEST_PROPERTY},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "deleted" in data
        assert data["deleted"] >= 2
        print(f"Cleared {data['deleted']} shifts")
        
        # Cleanup staff
        requests.delete(f"{BASE_URL}/api/shifts/staff/{staff['id']}", headers=auth_headers)
    
    def test_copy_week_shifts(self, auth_headers):
        """POST /api/shifts/bulk/copy-week - copy shifts to another week"""
        source_week = "2026-04-06"
        target_week = "2026-04-13"
        
        # Create staff and shifts for source week
        staff_payload = {"name": f"TEST_CopyStaff_{uuid.uuid4().hex[:8]}", "property_id": TEST_PROPERTY}
        staff_resp = requests.post(f"{BASE_URL}/api/shifts/staff", json=staff_payload, headers=auth_headers)
        staff = staff_resp.json()
        
        shift_ids = []
        for i in range(2):
            shift_payload = {
                "staff_id": staff["id"],
                "staff_name": staff["name"],
                "date": f"2026-04-0{6+i}",
                "week_start": source_week,
                "property_id": TEST_PROPERTY
            }
            resp = requests.post(f"{BASE_URL}/api/shifts/entries", json=shift_payload, headers=auth_headers)
            shift_ids.append(resp.json()["id"])
        
        # Copy week
        response = requests.post(
            f"{BASE_URL}/api/shifts/bulk/copy-week",
            json={"source_week": source_week, "target_week": target_week, "property_id": TEST_PROPERTY},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "copied" in data
        assert data["copied"] >= 2
        print(f"Copied {data['copied']} shifts")
        
        # Cleanup
        for sid in shift_ids:
            requests.delete(f"{BASE_URL}/api/shifts/entries/{sid}", headers=auth_headers)
        # Clear target week
        requests.post(
            f"{BASE_URL}/api/shifts/bulk/clear-week",
            json={"week_start": target_week, "property_id": TEST_PROPERTY},
            headers=auth_headers
        )
        requests.delete(f"{BASE_URL}/api/shifts/staff/{staff['id']}", headers=auth_headers)


class TestPayrollSummary(TestAuth):
    """Payroll Summary tests"""
    
    def test_payroll_summary(self, auth_headers):
        """GET /api/shifts/payroll/{property_id} - get payroll summary"""
        response = requests.get(f"{BASE_URL}/api/shifts/payroll/{TEST_PROPERTY}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        # If there are entries, verify structure
        if len(data) > 0:
            entry = data[0]
            assert "staff_id" in entry
            assert "staff_name" in entry
            assert "total_shifts" in entry
            assert "total_hours" in entry
            assert "total_pay" in entry
        print(f"Payroll summary: {len(data)} staff entries")
    
    def test_payroll_summary_with_week_filter(self, auth_headers):
        """GET /api/shifts/payroll/{property_id}?week_start= - filter by week"""
        response = requests.get(
            f"{BASE_URL}/api/shifts/payroll/{TEST_PROPERTY}?week_start=2026-01-20",
            headers=auth_headers
        )
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
