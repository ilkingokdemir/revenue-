"""
Iteration 77 - Team & Vendor Management Tests
Tests for internal team members and external vendors CRUD operations
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
PROPERTY_ID = "aldgate-flats"

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        data = response.json()
        return data.get("token") or data.get("access_token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def api_client(auth_token):
    """Session with auth header"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    return session


class TestTeamMembersCRUD:
    """Tests for /api/maintenance/team endpoints"""
    
    created_member_id = None
    
    def test_create_team_member(self, api_client):
        """POST /api/maintenance/team - creates team member"""
        payload = {
            "property_id": PROPERTY_ID,
            "name": f"TEST_John Smith {uuid.uuid4().hex[:6]}",
            "role": "technician",
            "phone": "+44 7700 900123",
            "email": "john.smith@test.com",
            "specialities": ["Plumbing", "Electrical"]
        }
        response = api_client.post(f"{BASE_URL}/api/maintenance/team", json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "id" in data, "Response should contain 'id'"
        assert data["name"] == payload["name"], "Name should match"
        assert data["role"] == "technician", "Role should be technician"
        assert data["phone"] == payload["phone"], "Phone should match"
        assert data["email"] == payload["email"], "Email should match"
        assert data["specialities"] == ["Plumbing", "Electrical"], "Specialities should match"
        assert data["is_active"] == True, "Should be active by default"
        assert data["type"] == "internal", "Type should be 'internal'"
        assert "created_at" in data, "Should have created_at"
        
        TestTeamMembersCRUD.created_member_id = data["id"]
        print(f"✓ Created team member: {data['name']} (ID: {data['id']})")
    
    def test_list_team_members(self, api_client):
        """GET /api/maintenance/team/{property_id} - lists team with workload"""
        response = api_client.get(f"{BASE_URL}/api/maintenance/team/{PROPERTY_ID}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert isinstance(data, list), "Response should be a list"
        
        # Find our created member
        created_member = next((m for m in data if m.get("id") == TestTeamMembersCRUD.created_member_id), None)
        assert created_member is not None, "Created member should be in list"
        
        # Verify workload fields are attached
        assert "open_issues" in created_member, "Should have open_issues count"
        assert "total_resolved" in created_member, "Should have total_resolved count"
        assert isinstance(created_member["open_issues"], int), "open_issues should be int"
        assert isinstance(created_member["total_resolved"], int), "total_resolved should be int"
        
        print(f"✓ Listed {len(data)} team members with workload data")
    
    def test_list_team_all_properties(self, api_client):
        """GET /api/maintenance/team/all - lists team across all properties"""
        response = api_client.get(f"{BASE_URL}/api/maintenance/team/all")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ Listed {len(data)} team members across all properties")
    
    def test_update_team_member(self, api_client):
        """PUT /api/maintenance/team/{member_id} - updates team member"""
        assert TestTeamMembersCRUD.created_member_id, "Need created member ID"
        
        updates = {
            "role": "supervisor",
            "specialities": ["Plumbing", "Electrical", "HVAC"]
        }
        response = api_client.put(
            f"{BASE_URL}/api/maintenance/team/{TestTeamMembersCRUD.created_member_id}",
            json=updates
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert data["role"] == "supervisor", "Role should be updated to supervisor"
        assert "HVAC" in data["specialities"], "Specialities should include HVAC"
        print(f"✓ Updated team member role to supervisor")
    
    def test_toggle_team_member_active(self, api_client):
        """PUT /api/maintenance/team/{member_id} - toggle is_active"""
        assert TestTeamMembersCRUD.created_member_id, "Need created member ID"
        
        # Deactivate
        response = api_client.put(
            f"{BASE_URL}/api/maintenance/team/{TestTeamMembersCRUD.created_member_id}",
            json={"is_active": False}
        )
        assert response.status_code == 200
        assert response.json()["is_active"] == False, "Should be deactivated"
        
        # Reactivate
        response = api_client.put(
            f"{BASE_URL}/api/maintenance/team/{TestTeamMembersCRUD.created_member_id}",
            json={"is_active": True}
        )
        assert response.status_code == 200
        assert response.json()["is_active"] == True, "Should be reactivated"
        print(f"✓ Toggle active status works")
    
    def test_delete_team_member(self, api_client):
        """DELETE /api/maintenance/team/{member_id} - deletes team member"""
        assert TestTeamMembersCRUD.created_member_id, "Need created member ID"
        
        response = api_client.delete(
            f"{BASE_URL}/api/maintenance/team/{TestTeamMembersCRUD.created_member_id}"
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("status") == "deleted", "Should return deleted status"
        
        # Verify deletion
        list_response = api_client.get(f"{BASE_URL}/api/maintenance/team/{PROPERTY_ID}")
        members = list_response.json()
        deleted_member = next((m for m in members if m.get("id") == TestTeamMembersCRUD.created_member_id), None)
        assert deleted_member is None, "Deleted member should not be in list"
        
        print(f"✓ Deleted team member and verified removal")


class TestVendorsCRUD:
    """Tests for /api/maintenance/vendors endpoints"""
    
    created_vendor_id = None
    
    def test_create_vendor(self, api_client):
        """POST /api/maintenance/vendors - creates external vendor"""
        payload = {
            "property_id": PROPERTY_ID,
            "company_name": f"TEST_ABC Plumbing Ltd {uuid.uuid4().hex[:6]}",
            "contact_person": "Jane Doe",
            "phone": "+44 7700 900456",
            "email": "contact@abcplumbing.test",
            "specialities": ["Plumbing", "Drainage"],
            "hourly_rate": 75,
            "currency": "GBP",
            "notes": "Available 24/7 for emergencies"
        }
        response = api_client.post(f"{BASE_URL}/api/maintenance/vendors", json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "id" in data, "Response should contain 'id'"
        assert data["company_name"] == payload["company_name"], "Company name should match"
        assert data["contact_person"] == "Jane Doe", "Contact person should match"
        assert data["phone"] == payload["phone"], "Phone should match"
        assert data["email"] == payload["email"], "Email should match"
        assert data["specialities"] == ["Plumbing", "Drainage"], "Specialities should match"
        assert data["hourly_rate"] == 75, "Hourly rate should be 75"
        assert data["currency"] == "GBP", "Currency should be GBP"
        assert data["notes"] == payload["notes"], "Notes should match"
        assert data["is_active"] == True, "Should be active by default"
        assert data["type"] == "external", "Type should be 'external'"
        assert data["rating"] == 0, "Rating should default to 0"
        assert "created_at" in data, "Should have created_at"
        
        TestVendorsCRUD.created_vendor_id = data["id"]
        print(f"✓ Created vendor: {data['company_name']} (ID: {data['id']})")
    
    def test_list_vendors(self, api_client):
        """GET /api/maintenance/vendors/{property_id} - lists vendors with stats"""
        response = api_client.get(f"{BASE_URL}/api/maintenance/vendors/{PROPERTY_ID}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert isinstance(data, list), "Response should be a list"
        
        # Find our created vendor
        created_vendor = next((v for v in data if v.get("id") == TestVendorsCRUD.created_vendor_id), None)
        assert created_vendor is not None, "Created vendor should be in list"
        
        # Verify stats fields are attached
        assert "open_issues" in created_vendor, "Should have open_issues count"
        assert "total_resolved" in created_vendor, "Should have total_resolved count"
        assert "total_cost" in created_vendor, "Should have total_cost"
        assert isinstance(created_vendor["open_issues"], int), "open_issues should be int"
        assert isinstance(created_vendor["total_resolved"], int), "total_resolved should be int"
        assert isinstance(created_vendor["total_cost"], (int, float)), "total_cost should be numeric"
        
        print(f"✓ Listed {len(data)} vendors with stats (open_issues, total_resolved, total_cost)")
    
    def test_list_vendors_all_properties(self, api_client):
        """GET /api/maintenance/vendors/all - lists vendors across all properties"""
        response = api_client.get(f"{BASE_URL}/api/maintenance/vendors/all")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ Listed {len(data)} vendors across all properties")
    
    def test_update_vendor(self, api_client):
        """PUT /api/maintenance/vendors/{vendor_id} - updates vendor"""
        assert TestVendorsCRUD.created_vendor_id, "Need created vendor ID"
        
        updates = {
            "hourly_rate": 85,
            "specialities": ["Plumbing", "Drainage", "Heating"]
        }
        response = api_client.put(
            f"{BASE_URL}/api/maintenance/vendors/{TestVendorsCRUD.created_vendor_id}",
            json=updates
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert data["hourly_rate"] == 85, "Hourly rate should be updated to 85"
        assert "Heating" in data["specialities"], "Specialities should include Heating"
        print(f"✓ Updated vendor hourly rate to £85/h")
    
    def test_toggle_vendor_active(self, api_client):
        """PUT /api/maintenance/vendors/{vendor_id} - toggle is_active"""
        assert TestVendorsCRUD.created_vendor_id, "Need created vendor ID"
        
        # Deactivate
        response = api_client.put(
            f"{BASE_URL}/api/maintenance/vendors/{TestVendorsCRUD.created_vendor_id}",
            json={"is_active": False}
        )
        assert response.status_code == 200
        assert response.json()["is_active"] == False, "Should be deactivated"
        
        # Reactivate
        response = api_client.put(
            f"{BASE_URL}/api/maintenance/vendors/{TestVendorsCRUD.created_vendor_id}",
            json={"is_active": True}
        )
        assert response.status_code == 200
        assert response.json()["is_active"] == True, "Should be reactivated"
        print(f"✓ Toggle active status works")
    
    def test_delete_vendor(self, api_client):
        """DELETE /api/maintenance/vendors/{vendor_id} - deletes vendor"""
        assert TestVendorsCRUD.created_vendor_id, "Need created vendor ID"
        
        response = api_client.delete(
            f"{BASE_URL}/api/maintenance/vendors/{TestVendorsCRUD.created_vendor_id}"
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("status") == "deleted", "Should return deleted status"
        
        # Verify deletion
        list_response = api_client.get(f"{BASE_URL}/api/maintenance/vendors/{PROPERTY_ID}")
        vendors = list_response.json()
        deleted_vendor = next((v for v in vendors if v.get("id") == TestVendorsCRUD.created_vendor_id), None)
        assert deleted_vendor is None, "Deleted vendor should not be in list"
        
        print(f"✓ Deleted vendor and verified removal")


class TestAssigneesEndpoint:
    """Tests for /api/maintenance/assignees endpoint - combined team + vendors"""
    
    team_member_id = None
    vendor_id = None
    
    def test_setup_test_data(self, api_client):
        """Create test team member and vendor for assignees test"""
        # Create team member
        team_payload = {
            "property_id": PROPERTY_ID,
            "name": f"TEST_Assignee Team {uuid.uuid4().hex[:6]}",
            "role": "electrician",
            "specialities": ["Electrical", "Lighting"]
        }
        team_response = api_client.post(f"{BASE_URL}/api/maintenance/team", json=team_payload)
        assert team_response.status_code == 200
        TestAssigneesEndpoint.team_member_id = team_response.json()["id"]
        
        # Create vendor
        vendor_payload = {
            "property_id": PROPERTY_ID,
            "company_name": f"TEST_Assignee Vendor {uuid.uuid4().hex[:6]}",
            "contact_person": "Test Contact",
            "hourly_rate": 50,
            "specialities": ["HVAC"]
        }
        vendor_response = api_client.post(f"{BASE_URL}/api/maintenance/vendors", json=vendor_payload)
        assert vendor_response.status_code == 200
        TestAssigneesEndpoint.vendor_id = vendor_response.json()["id"]
        
        print(f"✓ Created test team member and vendor for assignees test")
    
    def test_list_assignees_combined(self, api_client):
        """GET /api/maintenance/assignees/{property_id} - returns combined list"""
        response = api_client.get(f"{BASE_URL}/api/maintenance/assignees/{PROPERTY_ID}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert isinstance(data, list), "Response should be a list"
        
        # Check for internal team members
        internal_assignees = [a for a in data if a.get("type") == "internal"]
        assert len(internal_assignees) > 0, "Should have internal team members"
        
        # Check for external vendors
        external_assignees = [a for a in data if a.get("type") == "external"]
        assert len(external_assignees) > 0, "Should have external vendors"
        
        # Verify structure of internal assignee
        internal = internal_assignees[0]
        assert "name" in internal, "Internal should have name"
        assert "type" in internal and internal["type"] == "internal", "Type should be internal"
        assert "role" in internal, "Internal should have role"
        assert "specialities" in internal, "Internal should have specialities"
        assert "open_issues" in internal, "Internal should have open_issues count"
        
        # Verify structure of external assignee
        external = external_assignees[0]
        assert "name" in external, "External should have name (company_name)"
        assert "type" in external and external["type"] == "external", "Type should be external"
        assert "role" in external and external["role"] == "vendor", "Role should be 'vendor'"
        assert "specialities" in external, "External should have specialities"
        assert "hourly_rate" in external, "External should have hourly_rate"
        assert "open_issues" in external, "External should have open_issues count"
        
        print(f"✓ Assignees endpoint returns {len(internal_assignees)} internal + {len(external_assignees)} external")
    
    def test_assignees_all_properties(self, api_client):
        """GET /api/maintenance/assignees/all - returns assignees across all properties"""
        response = api_client.get(f"{BASE_URL}/api/maintenance/assignees/all")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ Listed {len(data)} assignees across all properties")
    
    def test_cleanup_test_data(self, api_client):
        """Cleanup test data"""
        if TestAssigneesEndpoint.team_member_id:
            api_client.delete(f"{BASE_URL}/api/maintenance/team/{TestAssigneesEndpoint.team_member_id}")
        if TestAssigneesEndpoint.vendor_id:
            api_client.delete(f"{BASE_URL}/api/maintenance/vendors/{TestAssigneesEndpoint.vendor_id}")
        print(f"✓ Cleaned up test data")


class TestIssueAssignment:
    """Tests for assigning issues to team members or vendors"""
    
    team_member_id = None
    vendor_id = None
    issue_id = None
    team_name = None
    vendor_name = None
    
    def test_setup_assignment_data(self, api_client):
        """Create team member, vendor, and issue for assignment tests"""
        # Create team member
        team_name = f"TEST_Assignment Team {uuid.uuid4().hex[:6]}"
        team_response = api_client.post(f"{BASE_URL}/api/maintenance/team", json={
            "property_id": PROPERTY_ID,
            "name": team_name,
            "role": "plumber",
            "specialities": ["Plumbing"]
        })
        assert team_response.status_code == 200
        TestIssueAssignment.team_member_id = team_response.json()["id"]
        TestIssueAssignment.team_name = team_name
        
        # Create vendor
        vendor_name = f"TEST_Assignment Vendor {uuid.uuid4().hex[:6]}"
        vendor_response = api_client.post(f"{BASE_URL}/api/maintenance/vendors", json={
            "property_id": PROPERTY_ID,
            "company_name": vendor_name,
            "hourly_rate": 60,
            "specialities": ["Plumbing"]
        })
        assert vendor_response.status_code == 200
        TestIssueAssignment.vendor_id = vendor_response.json()["id"]
        TestIssueAssignment.vendor_name = vendor_name
        
        # Create issue
        issue_response = api_client.post(f"{BASE_URL}/api/maintenance/issues", json={
            "property_id": PROPERTY_ID,
            "title": f"TEST_Assignment Issue {uuid.uuid4().hex[:6]}",
            "category": "plumbing",
            "priority": "medium"
        })
        assert issue_response.status_code == 200
        TestIssueAssignment.issue_id = issue_response.json()["id"]
        
        print(f"✓ Created team member, vendor, and issue for assignment tests")
    
    def test_assign_to_team_member(self, api_client):
        """Assign issue to internal team member"""
        response = api_client.put(
            f"{BASE_URL}/api/maintenance/issues/{TestIssueAssignment.issue_id}",
            json={"assigned_to": TestIssueAssignment.team_name}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["assigned_to"] == TestIssueAssignment.team_name, "Should be assigned to team member"
        
        # Verify team member's open_issues count increased
        team_response = api_client.get(f"{BASE_URL}/api/maintenance/team/{PROPERTY_ID}")
        team_members = team_response.json()
        member = next((m for m in team_members if m["id"] == TestIssueAssignment.team_member_id), None)
        assert member is not None
        assert member["open_issues"] >= 1, "Team member should have at least 1 open issue"
        
        print(f"✓ Assigned issue to team member, open_issues count: {member['open_issues']}")
    
    def test_reassign_to_vendor(self, api_client):
        """Reassign issue to external vendor"""
        response = api_client.put(
            f"{BASE_URL}/api/maintenance/issues/{TestIssueAssignment.issue_id}",
            json={"assigned_to": TestIssueAssignment.vendor_name}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["assigned_to"] == TestIssueAssignment.vendor_name, "Should be assigned to vendor"
        
        # Verify vendor's open_issues count
        vendor_response = api_client.get(f"{BASE_URL}/api/maintenance/vendors/{PROPERTY_ID}")
        vendors = vendor_response.json()
        vendor = next((v for v in vendors if v["id"] == TestIssueAssignment.vendor_id), None)
        assert vendor is not None
        assert vendor["open_issues"] >= 1, "Vendor should have at least 1 open issue"
        
        print(f"✓ Reassigned issue to vendor, open_issues count: {vendor['open_issues']}")
    
    def test_cleanup_assignment_data(self, api_client):
        """Cleanup test data"""
        if TestIssueAssignment.issue_id:
            api_client.delete(f"{BASE_URL}/api/maintenance/issues/{TestIssueAssignment.issue_id}")
        if TestIssueAssignment.team_member_id:
            api_client.delete(f"{BASE_URL}/api/maintenance/team/{TestIssueAssignment.team_member_id}")
        if TestIssueAssignment.vendor_id:
            api_client.delete(f"{BASE_URL}/api/maintenance/vendors/{TestIssueAssignment.vendor_id}")
        print(f"✓ Cleaned up assignment test data")


class TestTeamMemberRoles:
    """Test all team member roles"""
    
    def test_all_roles_accepted(self, api_client):
        """Verify all role types are accepted"""
        roles = ["technician", "supervisor", "electrician", "plumber", "handyman", "hvac_tech"]
        
        for role in roles:
            payload = {
                "property_id": PROPERTY_ID,
                "name": f"TEST_Role {role} {uuid.uuid4().hex[:6]}",
                "role": role
            }
            response = api_client.post(f"{BASE_URL}/api/maintenance/team", json=payload)
            assert response.status_code == 200, f"Role '{role}' should be accepted"
            
            # Cleanup
            member_id = response.json()["id"]
            api_client.delete(f"{BASE_URL}/api/maintenance/team/{member_id}")
        
        print(f"✓ All {len(roles)} roles accepted: {', '.join(roles)}")
