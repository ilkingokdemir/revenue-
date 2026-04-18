"""
Iteration 143 - Payroll Rate Matrix & Bug Tracker API Tests
Tests:
- Payroll Rate Matrix: GET list, PUT cell, DELETE cell, filters, validation
- Bug Tracker: CRUD, comments, assignees, status/priority/type validation, access control
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# ============ FIXTURES ============

@pytest.fixture(scope="module")
def admin_token():
    """Get admin auth token"""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    return resp.json().get("token")

@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}

@pytest.fixture(scope="module")
def test_user_id(admin_headers):
    """Get a user ID for testing (admin user)"""
    resp = requests.get(f"{BASE_URL}/api/payroll-matrix", headers=admin_headers)
    assert resp.status_code == 200
    users = resp.json().get("users", [])
    assert len(users) > 0, "No users found for testing"
    return users[0]["id"]

@pytest.fixture(scope="module")
def test_property_id(admin_headers):
    """Get a property ID for testing"""
    resp = requests.get(f"{BASE_URL}/api/payroll-matrix", headers=admin_headers)
    assert resp.status_code == 200
    properties = resp.json().get("properties", [])
    assert len(properties) > 0, "No properties found for testing"
    return properties[0]["id"]


# ============ PAYROLL RATE MATRIX TESTS ============

class TestPayrollMatrixList:
    """GET /api/payroll-matrix - List matrix with filters"""
    
    def test_list_matrix_requires_auth(self):
        """Unauthenticated request returns 401"""
        resp = requests.get(f"{BASE_URL}/api/payroll-matrix")
        assert resp.status_code == 401
    
    def test_list_matrix_admin_success(self, admin_headers):
        """Admin can list matrix"""
        resp = requests.get(f"{BASE_URL}/api/payroll-matrix", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "properties" in data
        assert "users" in data
        assert "total_users" in data
        assert "total_configured_cells" in data
        assert "total_possible_cells" in data
        assert isinstance(data["properties"], list)
        assert isinstance(data["users"], list)
    
    def test_list_matrix_filter_by_q(self, admin_headers):
        """Filter by search query (name/email)"""
        resp = requests.get(f"{BASE_URL}/api/payroll-matrix?q=admin", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        # Should return users matching 'admin' in name or email
        for user in data["users"]:
            assert "admin" in user.get("name", "").lower() or "admin" in user.get("email", "").lower()
    
    def test_list_matrix_filter_by_role(self, admin_headers):
        """Filter by role"""
        resp = requests.get(f"{BASE_URL}/api/payroll-matrix?role=admin", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        for user in data["users"]:
            assert user.get("role") == "admin"
    
    def test_list_matrix_filter_by_property_id(self, admin_headers, test_property_id):
        """Filter by property_id (users with access to that property)"""
        resp = requests.get(f"{BASE_URL}/api/payroll-matrix?property_id={test_property_id}", headers=admin_headers)
        assert resp.status_code == 200
        # Should return 200 even if no users have access to that property


class TestPayrollMatrixUpdateCell:
    """PUT /api/payroll-matrix/{user_id}/{property_id} - Update cell"""
    
    def test_update_cell_requires_admin(self, admin_headers, test_user_id, test_property_id):
        """Only admin can update cells"""
        # First verify admin can update
        resp = requests.put(
            f"{BASE_URL}/api/payroll-matrix/{test_user_id}/{test_property_id}",
            headers=admin_headers,
            json={"payment_type": "hourly", "rate": 15.50, "split": False, "active": True}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") == True
    
    def test_update_cell_hourly_rate(self, admin_headers, test_user_id, test_property_id):
        """Update cell with hourly rate"""
        resp = requests.put(
            f"{BASE_URL}/api/payroll-matrix/{test_user_id}/{test_property_id}",
            headers=admin_headers,
            json={"payment_type": "hourly", "rate": 12.75, "split": False, "active": True}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") == True
        cell = data.get("cell")
        assert cell is not None
        assert cell["payment_type"] == "hourly"
        assert cell["rate"] == 12.75
        assert cell["split"] == False
        assert cell["active"] == True
    
    def test_update_cell_daily_rate_with_split(self, admin_headers, test_user_id, test_property_id):
        """Update cell with daily rate and split enabled"""
        resp = requests.put(
            f"{BASE_URL}/api/payroll-matrix/{test_user_id}/{test_property_id}",
            headers=admin_headers,
            json={"payment_type": "daily", "rate": 150.00, "split": True, "active": True}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") == True
        cell = data.get("cell")
        assert cell["payment_type"] == "daily"
        assert cell["rate"] == 150.00
        assert cell["split"] == True
    
    def test_update_cell_invalid_payment_type(self, admin_headers, test_user_id, test_property_id):
        """Invalid payment_type returns 400"""
        resp = requests.put(
            f"{BASE_URL}/api/payroll-matrix/{test_user_id}/{test_property_id}",
            headers=admin_headers,
            json={"payment_type": "weekly", "rate": 100}
        )
        assert resp.status_code == 400
        assert "hourly or daily" in resp.json().get("detail", "").lower()
    
    def test_update_cell_negative_rate(self, admin_headers, test_user_id, test_property_id):
        """Negative rate returns 400"""
        resp = requests.put(
            f"{BASE_URL}/api/payroll-matrix/{test_user_id}/{test_property_id}",
            headers=admin_headers,
            json={"payment_type": "hourly", "rate": -10}
        )
        assert resp.status_code == 400
        assert "negative" in resp.json().get("detail", "").lower()
    
    def test_update_cell_user_not_found(self, admin_headers, test_property_id):
        """Bogus user_id returns 404"""
        fake_user_id = str(uuid.uuid4())
        resp = requests.put(
            f"{BASE_URL}/api/payroll-matrix/{fake_user_id}/{test_property_id}",
            headers=admin_headers,
            json={"payment_type": "hourly", "rate": 10}
        )
        assert resp.status_code == 404
        assert "not found" in resp.json().get("detail", "").lower()
    
    def test_update_cell_zero_rate_inactive_deletes(self, admin_headers, test_user_id, test_property_id):
        """Setting rate=0 and active=false removes the cell"""
        # First set a rate
        requests.put(
            f"{BASE_URL}/api/payroll-matrix/{test_user_id}/{test_property_id}",
            headers=admin_headers,
            json={"payment_type": "hourly", "rate": 20, "active": True}
        )
        # Now set rate=0 and active=false
        resp = requests.put(
            f"{BASE_URL}/api/payroll-matrix/{test_user_id}/{test_property_id}",
            headers=admin_headers,
            json={"payment_type": "hourly", "rate": 0, "active": False}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") == True
        # Cell should be None (deleted)
        assert data.get("cell") is None


class TestPayrollMatrixDeleteCell:
    """DELETE /api/payroll-matrix/{user_id}/{property_id} - Delete cell"""
    
    def test_delete_cell_admin_success(self, admin_headers, test_user_id, test_property_id):
        """Admin can delete cell"""
        # First create a cell
        requests.put(
            f"{BASE_URL}/api/payroll-matrix/{test_user_id}/{test_property_id}",
            headers=admin_headers,
            json={"payment_type": "hourly", "rate": 25, "active": True}
        )
        # Delete it
        resp = requests.delete(
            f"{BASE_URL}/api/payroll-matrix/{test_user_id}/{test_property_id}",
            headers=admin_headers
        )
        assert resp.status_code == 200
        assert resp.json().get("ok") == True
    
    def test_delete_cell_user_not_found(self, admin_headers, test_property_id):
        """Bogus user_id returns 404"""
        fake_user_id = str(uuid.uuid4())
        resp = requests.delete(
            f"{BASE_URL}/api/payroll-matrix/{fake_user_id}/{test_property_id}",
            headers=admin_headers
        )
        assert resp.status_code == 404
    
    def test_delete_cell_idempotent(self, admin_headers, test_user_id, test_property_id):
        """Deleting non-existent cell returns ok (idempotent)"""
        # Delete twice
        requests.delete(
            f"{BASE_URL}/api/payroll-matrix/{test_user_id}/{test_property_id}",
            headers=admin_headers
        )
        resp = requests.delete(
            f"{BASE_URL}/api/payroll-matrix/{test_user_id}/{test_property_id}",
            headers=admin_headers
        )
        assert resp.status_code == 200
        assert resp.json().get("ok") == True


# ============ BUG TRACKER TESTS ============

class TestBugTrackerCreate:
    """POST /api/bug-tracker - Create ticket"""
    
    def test_create_ticket_requires_auth(self):
        """Unauthenticated request returns 401"""
        resp = requests.post(f"{BASE_URL}/api/bug-tracker", json={
            "title": "Test bug",
            "type": "bug",
            "priority": "medium"
        })
        assert resp.status_code == 401
    
    def test_create_ticket_success(self, admin_headers):
        """Create ticket with valid data"""
        resp = requests.post(f"{BASE_URL}/api/bug-tracker", headers=admin_headers, json={
            "title": "TEST_Bug: Login button not working",
            "description": "When clicking login, nothing happens",
            "type": "bug",
            "priority": "high",
            "area": "Bookings"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert data["title"] == "TEST_Bug: Login button not working"
        assert data["type"] == "bug"
        assert data["priority"] == "high"
        assert data["status"] == "new"
        assert data["created_by_id"] is not None
        assert data["created_by_name"] is not None
        assert data["created_by_role"] == "admin"
        return data["id"]
    
    def test_create_ticket_invalid_type(self, admin_headers):
        """Invalid type returns 400"""
        resp = requests.post(f"{BASE_URL}/api/bug-tracker", headers=admin_headers, json={
            "title": "Test ticket",
            "type": "invalid_type"
        })
        assert resp.status_code == 400
        assert "type" in resp.json().get("detail", "").lower()
    
    def test_create_ticket_invalid_priority(self, admin_headers):
        """Invalid priority returns 400"""
        resp = requests.post(f"{BASE_URL}/api/bug-tracker", headers=admin_headers, json={
            "title": "Test ticket",
            "priority": "super_urgent"
        })
        assert resp.status_code == 400
        assert "priority" in resp.json().get("detail", "").lower()
    
    def test_create_ticket_title_too_short(self, admin_headers):
        """Title < 3 chars returns 422"""
        resp = requests.post(f"{BASE_URL}/api/bug-tracker", headers=admin_headers, json={
            "title": "AB"
        })
        assert resp.status_code == 422  # Pydantic validation


class TestBugTrackerList:
    """GET /api/bug-tracker - List tickets with filters"""
    
    def test_list_tickets_requires_auth(self):
        """Unauthenticated request returns 401"""
        resp = requests.get(f"{BASE_URL}/api/bug-tracker")
        assert resp.status_code == 401
    
    def test_list_tickets_success(self, admin_headers):
        """Admin can list all tickets"""
        resp = requests.get(f"{BASE_URL}/api/bug-tracker", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "tickets" in data
        assert "stats" in data
        assert "total" in data["stats"]
        assert "new" in data["stats"]
        assert "in_progress" in data["stats"]
        assert "resolved" in data["stats"]
        assert "critical" in data["stats"]
        assert "by_status" in data["stats"]
    
    def test_list_tickets_filter_by_status(self, admin_headers):
        """Filter by status"""
        resp = requests.get(f"{BASE_URL}/api/bug-tracker?status=new", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        for ticket in data["tickets"]:
            assert ticket["status"] == "new"
    
    def test_list_tickets_filter_by_priority(self, admin_headers):
        """Filter by priority"""
        resp = requests.get(f"{BASE_URL}/api/bug-tracker?priority=high", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        for ticket in data["tickets"]:
            assert ticket["priority"] == "high"
    
    def test_list_tickets_filter_by_type(self, admin_headers):
        """Filter by type"""
        resp = requests.get(f"{BASE_URL}/api/bug-tracker?type=bug", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        for ticket in data["tickets"]:
            assert ticket["type"] == "bug"
    
    def test_list_tickets_filter_by_q(self, admin_headers):
        """Filter by search query"""
        resp = requests.get(f"{BASE_URL}/api/bug-tracker?q=TEST_Bug", headers=admin_headers)
        assert resp.status_code == 200


class TestBugTrackerGetOne:
    """GET /api/bug-tracker/{id} - Get single ticket"""
    
    @pytest.fixture
    def created_ticket_id(self, admin_headers):
        """Create a ticket for testing"""
        resp = requests.post(f"{BASE_URL}/api/bug-tracker", headers=admin_headers, json={
            "title": "TEST_GetOne: Test ticket for get",
            "type": "feedback",
            "priority": "low"
        })
        return resp.json()["id"]
    
    def test_get_ticket_success(self, admin_headers, created_ticket_id):
        """Get ticket by ID"""
        resp = requests.get(f"{BASE_URL}/api/bug-tracker/{created_ticket_id}", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == created_ticket_id
        assert data["title"] == "TEST_GetOne: Test ticket for get"
    
    def test_get_ticket_not_found(self, admin_headers):
        """Non-existent ticket returns 404"""
        fake_id = str(uuid.uuid4())
        resp = requests.get(f"{BASE_URL}/api/bug-tracker/{fake_id}", headers=admin_headers)
        assert resp.status_code == 404


class TestBugTrackerUpdate:
    """PUT /api/bug-tracker/{id} - Update ticket (triage)"""
    
    @pytest.fixture
    def ticket_for_update(self, admin_headers):
        """Create a ticket for update testing"""
        resp = requests.post(f"{BASE_URL}/api/bug-tracker", headers=admin_headers, json={
            "title": "TEST_Update: Ticket for update tests",
            "type": "bug",
            "priority": "medium"
        })
        return resp.json()["id"]
    
    def test_update_status(self, admin_headers, ticket_for_update):
        """Update ticket status"""
        resp = requests.put(
            f"{BASE_URL}/api/bug-tracker/{ticket_for_update}",
            headers=admin_headers,
            json={"status": "triaged"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "triaged"
    
    def test_update_priority(self, admin_headers, ticket_for_update):
        """Update ticket priority"""
        resp = requests.put(
            f"{BASE_URL}/api/bug-tracker/{ticket_for_update}",
            headers=admin_headers,
            json={"priority": "critical"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["priority"] == "critical"
    
    def test_update_type(self, admin_headers, ticket_for_update):
        """Update ticket type"""
        resp = requests.put(
            f"{BASE_URL}/api/bug-tracker/{ticket_for_update}",
            headers=admin_headers,
            json={"type": "feature_request"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "feature_request"
    
    def test_update_area(self, admin_headers, ticket_for_update):
        """Update ticket area"""
        resp = requests.put(
            f"{BASE_URL}/api/bug-tracker/{ticket_for_update}",
            headers=admin_headers,
            json={"area": "Payroll"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["area"] == "Payroll"
    
    def test_update_resolved_stamps_fields(self, admin_headers, ticket_for_update):
        """Setting status=resolved stamps resolved_at and resolved_by"""
        resp = requests.put(
            f"{BASE_URL}/api/bug-tracker/{ticket_for_update}",
            headers=admin_headers,
            json={"status": "resolved", "resolution_note": "Fixed the issue"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "resolved"
        assert data["resolved_at"] is not None
        assert data["resolved_by_id"] is not None
        assert data["resolved_by_name"] is not None
        assert data["resolution_note"] == "Fixed the issue"
    
    def test_update_invalid_status(self, admin_headers, ticket_for_update):
        """Invalid status returns 400"""
        resp = requests.put(
            f"{BASE_URL}/api/bug-tracker/{ticket_for_update}",
            headers=admin_headers,
            json={"status": "invalid_status"}
        )
        assert resp.status_code == 400
    
    def test_update_invalid_priority(self, admin_headers, ticket_for_update):
        """Invalid priority returns 400"""
        resp = requests.put(
            f"{BASE_URL}/api/bug-tracker/{ticket_for_update}",
            headers=admin_headers,
            json={"priority": "super_high"}
        )
        assert resp.status_code == 400
    
    def test_update_bogus_assignee(self, admin_headers, ticket_for_update):
        """Bogus assigned_to_id returns 400"""
        fake_id = str(uuid.uuid4())
        resp = requests.put(
            f"{BASE_URL}/api/bug-tracker/{ticket_for_update}",
            headers=admin_headers,
            json={"assigned_to_id": fake_id}
        )
        assert resp.status_code == 400
        assert "assignee" in resp.json().get("detail", "").lower()
    
    def test_update_clear_assignee(self, admin_headers, ticket_for_update):
        """Empty assigned_to_id clears assignee"""
        resp = requests.put(
            f"{BASE_URL}/api/bug-tracker/{ticket_for_update}",
            headers=admin_headers,
            json={"assigned_to_id": ""}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["assigned_to_id"] is None
        assert data["assigned_to_name"] is None
    
    def test_update_not_found(self, admin_headers):
        """Non-existent ticket returns 404"""
        fake_id = str(uuid.uuid4())
        resp = requests.put(
            f"{BASE_URL}/api/bug-tracker/{fake_id}",
            headers=admin_headers,
            json={"status": "triaged"}
        )
        assert resp.status_code == 404


class TestBugTrackerComments:
    """POST /api/bug-tracker/{id}/comments - Add comment"""
    
    @pytest.fixture
    def ticket_for_comments(self, admin_headers):
        """Create a ticket for comment testing"""
        resp = requests.post(f"{BASE_URL}/api/bug-tracker", headers=admin_headers, json={
            "title": "TEST_Comments: Ticket for comment tests",
            "type": "bug"
        })
        return resp.json()["id"]
    
    def test_add_comment_success(self, admin_headers, ticket_for_comments):
        """Add comment to ticket"""
        resp = requests.post(
            f"{BASE_URL}/api/bug-tracker/{ticket_for_comments}/comments",
            headers=admin_headers,
            json={"body": "This is a test comment"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert data["body"] == "This is a test comment"
        assert data["author_id"] is not None
        assert data["author_name"] is not None
        assert data["author_role"] == "admin"
        assert data["created_at"] is not None
    
    def test_add_comment_verify_in_ticket(self, admin_headers, ticket_for_comments):
        """Verify comment appears in ticket"""
        # Add comment
        requests.post(
            f"{BASE_URL}/api/bug-tracker/{ticket_for_comments}/comments",
            headers=admin_headers,
            json={"body": "Verification comment"}
        )
        # Get ticket
        resp = requests.get(f"{BASE_URL}/api/bug-tracker/{ticket_for_comments}", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["comments"]) > 0
        assert any(c["body"] == "Verification comment" for c in data["comments"])
    
    def test_add_comment_not_found(self, admin_headers):
        """Comment on non-existent ticket returns 404"""
        fake_id = str(uuid.uuid4())
        resp = requests.post(
            f"{BASE_URL}/api/bug-tracker/{fake_id}/comments",
            headers=admin_headers,
            json={"body": "Test comment"}
        )
        assert resp.status_code == 404


class TestBugTrackerDelete:
    """DELETE /api/bug-tracker/{id} - Delete ticket (admin only)"""
    
    def test_delete_ticket_admin_success(self, admin_headers):
        """Admin can delete ticket"""
        # Create ticket
        create_resp = requests.post(f"{BASE_URL}/api/bug-tracker", headers=admin_headers, json={
            "title": "TEST_Delete: Ticket to delete",
            "type": "bug"
        })
        ticket_id = create_resp.json()["id"]
        
        # Delete it
        resp = requests.delete(f"{BASE_URL}/api/bug-tracker/{ticket_id}", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json().get("ok") == True
        
        # Verify deleted
        get_resp = requests.get(f"{BASE_URL}/api/bug-tracker/{ticket_id}", headers=admin_headers)
        assert get_resp.status_code == 404
    
    def test_delete_ticket_not_found(self, admin_headers):
        """Delete non-existent ticket returns 404"""
        fake_id = str(uuid.uuid4())
        resp = requests.delete(f"{BASE_URL}/api/bug-tracker/{fake_id}", headers=admin_headers)
        assert resp.status_code == 404


class TestBugTrackerAssignees:
    """GET /api/bug-tracker-meta/assignees - Get assignable users"""
    
    def test_get_assignees_requires_auth(self):
        """Unauthenticated request returns 401"""
        resp = requests.get(f"{BASE_URL}/api/bug-tracker-meta/assignees")
        assert resp.status_code == 401
    
    def test_get_assignees_success(self, admin_headers):
        """Get list of assignable users (admin/manager only)"""
        resp = requests.get(f"{BASE_URL}/api/bug-tracker-meta/assignees", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # All returned users should be admin or manager
        for user in data:
            assert user["role"] in ["admin", "manager"]
            assert "id" in user
            assert "name" in user
            assert "email" in user


class TestBugTrackerAssignment:
    """Test assigning tickets to users"""
    
    @pytest.fixture
    def ticket_for_assignment(self, admin_headers):
        """Create a ticket for assignment testing"""
        resp = requests.post(f"{BASE_URL}/api/bug-tracker", headers=admin_headers, json={
            "title": "TEST_Assignment: Ticket for assignment tests",
            "type": "bug"
        })
        return resp.json()["id"]
    
    def test_assign_to_admin(self, admin_headers, ticket_for_assignment):
        """Assign ticket to admin user"""
        # Get assignees
        assignees_resp = requests.get(f"{BASE_URL}/api/bug-tracker-meta/assignees", headers=admin_headers)
        assignees = assignees_resp.json()
        assert len(assignees) > 0
        
        admin_user = next((a for a in assignees if a["role"] == "admin"), None)
        assert admin_user is not None
        
        # Assign
        resp = requests.put(
            f"{BASE_URL}/api/bug-tracker/{ticket_for_assignment}",
            headers=admin_headers,
            json={"assigned_to_id": admin_user["id"]}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["assigned_to_id"] == admin_user["id"]
        assert data["assigned_to_name"] == admin_user["name"]


# ============ CLEANUP ============

class TestCleanup:
    """Cleanup test data"""
    
    def test_cleanup_test_tickets(self, admin_headers):
        """Delete all TEST_ prefixed tickets"""
        resp = requests.get(f"{BASE_URL}/api/bug-tracker?q=TEST_", headers=admin_headers)
        if resp.status_code == 200:
            tickets = resp.json().get("tickets", [])
            for ticket in tickets:
                if ticket["title"].startswith("TEST_"):
                    requests.delete(f"{BASE_URL}/api/bug-tracker/{ticket['id']}", headers=admin_headers)
        print(f"Cleaned up {len(tickets) if resp.status_code == 200 else 0} test tickets")
