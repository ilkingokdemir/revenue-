"""
Iteration 86 - Staff Management Panel Backend Tests
Tests for:
- GET /api/admin/users - List users with permissions
- GET /api/admin/users/{user_id} - Get single user detail
- PUT /api/admin/users/{user_id}/permissions - Update user with branch_payments, color, name
- GET /api/admin/roles - List roles with user counts and permission counts
- GET /api/admin/my-shifts - Get shifts for current user
- POST /api/auth/register - Create user with id field
- VALID_ROLES includes housekeeper and maintenance
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://review-hub-108.preview.emergentagent.com')

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
STAFF_EMAIL = "ali@hotel.com"
STAFF_PASSWORD = "Staff2026!"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    assert response.status_code == 200, f"Admin login failed: {response.text}"
    return response.json()["token"]


@pytest.fixture(scope="module")
def staff_token():
    """Get staff (Ali) authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": STAFF_EMAIL,
        "password": STAFF_PASSWORD
    })
    assert response.status_code == 200, f"Staff login failed: {response.text}"
    return response.json()["token"]


class TestAdminUsersEndpoint:
    """Tests for GET /api/admin/users"""
    
    def test_list_users_returns_users_with_permissions(self, admin_token):
        """GET /api/admin/users returns users with effective_permissions"""
        response = requests.get(
            f"{BASE_URL}/api/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        users = response.json()
        assert isinstance(users, list)
        assert len(users) >= 1  # At least admin user
        
        # Check admin user has effective_permissions
        admin_user = next((u for u in users if u["email"] == ADMIN_EMAIL), None)
        assert admin_user is not None
        assert "effective_permissions" in admin_user
        assert "dashboard" in admin_user["effective_permissions"]
    
    def test_list_users_includes_branch_payments(self, admin_token):
        """GET /api/admin/users returns users with branch_payments field"""
        response = requests.get(
            f"{BASE_URL}/api/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        users = response.json()
        
        # Find Ali user who has branch_payments
        ali_user = next((u for u in users if u["email"] == STAFF_EMAIL), None)
        assert ali_user is not None
        assert "branch_payments" in ali_user
        assert "aldgate-flats" in ali_user["branch_payments"]
        assert ali_user["branch_payments"]["aldgate-flats"]["rate"] == 50
    
    def test_list_users_requires_auth(self):
        """GET /api/admin/users requires authentication"""
        response = requests.get(f"{BASE_URL}/api/admin/users")
        assert response.status_code == 401


class TestUserDetailEndpoint:
    """Tests for GET /api/admin/users/{user_id}"""
    
    def test_get_user_detail(self, admin_token):
        """GET /api/admin/users/{user_id} returns single user"""
        # First get user list to find Ali's ID
        list_response = requests.get(
            f"{BASE_URL}/api/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        users = list_response.json()
        ali_user = next((u for u in users if u["email"] == STAFF_EMAIL), None)
        assert ali_user is not None
        
        # Get user detail
        response = requests.get(
            f"{BASE_URL}/api/admin/users/{ali_user['id']}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        user = response.json()
        assert user["email"] == STAFF_EMAIL
        assert user["name"] == "Ali"
        assert "branch_payments" in user
        assert "property_access" in user
    
    def test_get_user_detail_not_found(self, admin_token):
        """GET /api/admin/users/{user_id} returns 404 for non-existent user"""
        response = requests.get(
            f"{BASE_URL}/api/admin/users/non-existent-id",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 404


class TestUpdateUserPermissions:
    """Tests for PUT /api/admin/users/{user_id}/permissions"""
    
    def test_update_user_branch_payments(self, admin_token):
        """PUT /api/admin/users/{user_id}/permissions updates branch_payments"""
        # Get Ali's ID
        list_response = requests.get(
            f"{BASE_URL}/api/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        users = list_response.json()
        ali_user = next((u for u in users if u["email"] == STAFF_EMAIL), None)
        
        # Update branch_payments
        new_branch_payments = {
            "aldgate-flats": {"type": "daily", "rate": 55},
            "vilenza-hotel": {"type": "daily", "rate": 105}
        }
        response = requests.put(
            f"{BASE_URL}/api/admin/users/{ali_user['id']}/permissions",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"branch_payments": new_branch_payments}
        )
        assert response.status_code == 200
        updated = response.json()
        assert updated["branch_payments"]["aldgate-flats"]["rate"] == 55
        
        # Revert to original
        requests.put(
            f"{BASE_URL}/api/admin/users/{ali_user['id']}/permissions",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"branch_payments": {
                "aldgate-flats": {"type": "daily", "rate": 50},
                "vilenza-hotel": {"type": "daily", "rate": 100}
            }}
        )
    
    def test_update_user_color(self, admin_token):
        """PUT /api/admin/users/{user_id}/permissions updates color"""
        list_response = requests.get(
            f"{BASE_URL}/api/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        users = list_response.json()
        ali_user = next((u for u in users if u["email"] == STAFF_EMAIL), None)
        
        response = requests.put(
            f"{BASE_URL}/api/admin/users/{ali_user['id']}/permissions",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"color": "#ff0000"}
        )
        assert response.status_code == 200
        assert response.json()["color"] == "#ff0000"
        
        # Revert
        requests.put(
            f"{BASE_URL}/api/admin/users/{ali_user['id']}/permissions",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"color": "#e74c3c"}
        )
    
    def test_update_user_name(self, admin_token):
        """PUT /api/admin/users/{user_id}/permissions updates name"""
        list_response = requests.get(
            f"{BASE_URL}/api/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        users = list_response.json()
        ali_user = next((u for u in users if u["email"] == STAFF_EMAIL), None)
        
        response = requests.put(
            f"{BASE_URL}/api/admin/users/{ali_user['id']}/permissions",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "Ali Test"}
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Ali Test"
        
        # Revert
        requests.put(
            f"{BASE_URL}/api/admin/users/{ali_user['id']}/permissions",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "Ali"}
        )
    
    def test_update_user_does_not_return_password_hash(self, admin_token):
        """PUT /api/admin/users/{user_id}/permissions does not return password_hash"""
        list_response = requests.get(
            f"{BASE_URL}/api/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        users = list_response.json()
        ali_user = next((u for u in users if u["email"] == STAFF_EMAIL), None)
        
        response = requests.put(
            f"{BASE_URL}/api/admin/users/{ali_user['id']}/permissions",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"color": "#e74c3c"}
        )
        assert response.status_code == 200
        assert "password_hash" not in response.json()


class TestRolesEndpoint:
    """Tests for GET /api/admin/roles"""
    
    def test_list_roles_returns_builtin_roles(self, admin_token):
        """GET /api/admin/roles returns built-in roles"""
        response = requests.get(
            f"{BASE_URL}/api/admin/roles",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "roles" in data
        assert "modules" in data
        assert "actions" in data
        
        roles = data["roles"]
        role_ids = [r["id"] for r in roles]
        assert "admin" in role_ids
        assert "manager" in role_ids
        assert "receptionist" in role_ids
    
    def test_roles_have_permissions(self, admin_token):
        """GET /api/admin/roles returns roles with permissions"""
        response = requests.get(
            f"{BASE_URL}/api/admin/roles",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        data = response.json()
        admin_role = next((r for r in data["roles"] if r["id"] == "admin"), None)
        assert admin_role is not None
        assert "permissions" in admin_role
        assert "dashboard" in admin_role["permissions"]
        assert "view" in admin_role["permissions"]["dashboard"]


class TestMyShiftsEndpoint:
    """Tests for GET /api/admin/my-shifts"""
    
    def test_my_shifts_returns_empty_for_no_shifts(self, admin_token):
        """GET /api/admin/my-shifts returns empty array when no shifts"""
        response = requests.get(
            f"{BASE_URL}/api/admin/my-shifts",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    def test_my_shifts_accessible_by_maintenance_role(self, staff_token):
        """GET /api/admin/my-shifts is accessible by maintenance role"""
        response = requests.get(
            f"{BASE_URL}/api/admin/my-shifts",
            headers={"Authorization": f"Bearer {staff_token}"}
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    def test_my_shifts_requires_auth(self):
        """GET /api/admin/my-shifts requires authentication"""
        response = requests.get(f"{BASE_URL}/api/admin/my-shifts")
        assert response.status_code == 401


class TestUserCreation:
    """Tests for POST /api/auth/register"""
    
    def test_create_user_returns_id(self, admin_token):
        """POST /api/auth/register returns user with id field"""
        test_email = "test_iteration86@hotel.com"
        
        # Create user
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "email": test_email,
                "password": "TestPass123!",
                "name": "TEST_Iteration86",
                "role": "receptionist",
                "department": "front_desk"
            }
        )
        
        if response.status_code == 400 and "already registered" in response.text:
            # User already exists, delete and recreate
            users = requests.get(
                f"{BASE_URL}/api/admin/users",
                headers={"Authorization": f"Bearer {admin_token}"}
            ).json()
            test_user = next((u for u in users if u["email"] == test_email), None)
            if test_user:
                requests.delete(
                    f"{BASE_URL}/api/users/{test_user['id']}",
                    headers={"Authorization": f"Bearer {admin_token}"}
                )
            response = requests.post(
                f"{BASE_URL}/api/auth/register",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={
                    "email": test_email,
                    "password": "TestPass123!",
                    "name": "TEST_Iteration86",
                    "role": "receptionist",
                    "department": "front_desk"
                }
            )
        
        assert response.status_code == 200
        user = response.json()
        assert "id" in user
        
        # Cleanup
        requests.delete(
            f"{BASE_URL}/api/users/{user['id']}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )


class TestValidRoles:
    """Tests for VALID_ROLES configuration"""
    
    def test_housekeeper_role_valid(self, admin_token):
        """housekeeper is a valid role"""
        test_email = "test_housekeeper86@hotel.com"
        
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "email": test_email,
                "password": "TestPass123!",
                "name": "TEST_Housekeeper",
                "role": "housekeeper",
                "department": "housekeeping"
            }
        )
        
        if response.status_code == 400 and "already registered" in response.text:
            pytest.skip("User already exists")
        
        assert response.status_code == 200
        user = response.json()
        
        # Cleanup
        requests.delete(
            f"{BASE_URL}/api/users/{user['id']}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
    
    def test_maintenance_role_valid(self, admin_token):
        """maintenance is a valid role"""
        test_email = "test_maintenance86@hotel.com"
        
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "email": test_email,
                "password": "TestPass123!",
                "name": "TEST_Maintenance",
                "role": "maintenance",
                "department": "maintenance"
            }
        )
        
        if response.status_code == 400 and "already registered" in response.text:
            pytest.skip("User already exists")
        
        assert response.status_code == 200
        user = response.json()
        
        # Cleanup
        requests.delete(
            f"{BASE_URL}/api/users/{user['id']}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )


class TestStaffLogin:
    """Tests for staff login functionality"""
    
    def test_staff_can_login(self):
        """Staff user (Ali) can log in"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": STAFF_EMAIL,
            "password": STAFF_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == STAFF_EMAIL
        assert data["role"] == "maintenance"
        assert "token" in data
