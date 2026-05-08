"""
Iteration 146 - RBAC Permission Enforcement Tests
Tests for:
1. GET /api/rbac/me/permissions - returns user's effective permissions + menu_permissions
2. require_perm() middleware - blocks non-admin users without specific permissions
3. POST/PUT/DELETE /api/rbac/roles - now require create_roles/edit_roles/delete_roles permissions
4. Legacy admin role bypasses all permission checks
5. Receptionist (sarah@hotel.test) gets limited permissions (19 perms + 7 menu)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials from test_credentials.md
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
RECEPTIONIST_EMAIL = "sarah@hotel.test"
RECEPTIONIST_PASSWORD = "StaffP@ss1"


class TestRBACMePermissions:
    """Tests for GET /api/rbac/me/permissions endpoint"""

    @pytest.fixture(scope="class")
    def admin_session(self):
        """Login as admin and return session"""
        session = requests.Session()
        resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert resp.status_code == 200, f"Admin login failed: {resp.text}"
        return session

    @pytest.fixture(scope="class")
    def receptionist_session(self):
        """Login as receptionist (sarah) and return session"""
        session = requests.Session()
        resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": RECEPTIONIST_EMAIL,
            "password": RECEPTIONIST_PASSWORD
        })
        assert resp.status_code == 200, f"Receptionist login failed: {resp.text}"
        return session

    def test_me_permissions_requires_auth(self):
        """GET /api/rbac/me/permissions requires authentication"""
        resp = requests.get(f"{BASE_URL}/api/rbac/me/permissions")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

    def test_admin_gets_all_permissions(self, admin_session):
        """Admin user gets 313+ permissions and 71+ menu permissions"""
        resp = admin_session.get(f"{BASE_URL}/api/rbac/me/permissions")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        # Verify response structure
        assert "user_id" in data
        assert "role" in data
        assert "role_key" in data
        assert "is_legacy_admin" in data
        assert "permissions" in data
        assert "menu_permissions" in data
        assert "total_permissions" in data
        
        # Admin should have is_legacy_admin=True
        assert data["is_legacy_admin"] == True, f"Admin should have is_legacy_admin=True, got {data['is_legacy_admin']}"
        assert data["role"] == "admin", f"Expected role=admin, got {data['role']}"
        
        # Admin should have 300+ permissions (main agent said 313)
        assert data["total_permissions"] >= 300, f"Admin should have 300+ perms, got {data['total_permissions']}"
        assert len(data["permissions"]) >= 300, f"Admin permissions list should have 300+ items"
        
        # Admin should have 70+ menu permissions (main agent said 71)
        assert len(data["menu_permissions"]) >= 70, f"Admin should have 70+ menu perms, got {len(data['menu_permissions'])}"
        
        print(f"✓ Admin has {data['total_permissions']} permissions and {len(data['menu_permissions'])} menu permissions")

    def test_receptionist_gets_limited_permissions(self, receptionist_session):
        """Receptionist (sarah) gets ~19 permissions and ~7 menu permissions"""
        resp = receptionist_session.get(f"{BASE_URL}/api/rbac/me/permissions")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        # Verify response structure
        assert "is_legacy_admin" in data
        assert "permissions" in data
        assert "menu_permissions" in data
        
        # Receptionist should NOT be legacy admin
        assert data["is_legacy_admin"] == False, f"Receptionist should not be legacy admin"
        assert data["role"] == "receptionist", f"Expected role=receptionist, got {data['role']}"
        
        # Receptionist should have limited permissions (main agent said 19 perms + 7 menu)
        # Allow some variance since templates may change
        assert data["total_permissions"] >= 10, f"Receptionist should have 10+ perms, got {data['total_permissions']}"
        assert data["total_permissions"] <= 50, f"Receptionist should have <50 perms, got {data['total_permissions']}"
        
        assert len(data["menu_permissions"]) >= 5, f"Receptionist should have 5+ menu perms, got {len(data['menu_permissions'])}"
        assert len(data["menu_permissions"]) <= 20, f"Receptionist should have <20 menu perms, got {len(data['menu_permissions'])}"
        
        print(f"✓ Receptionist has {data['total_permissions']} permissions and {len(data['menu_permissions'])} menu permissions")
        print(f"  Permissions: {data['permissions'][:10]}...")
        print(f"  Menu perms: {data['menu_permissions']}")


class TestRequirePermMiddleware:
    """Tests for require_perm() middleware on RBAC role endpoints"""

    @pytest.fixture(scope="class")
    def admin_session(self):
        """Login as admin and return session"""
        session = requests.Session()
        resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert resp.status_code == 200, f"Admin login failed: {resp.text}"
        return session

    @pytest.fixture(scope="class")
    def receptionist_session(self):
        """Login as receptionist (sarah) and return session"""
        session = requests.Session()
        resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": RECEPTIONIST_EMAIL,
            "password": RECEPTIONIST_PASSWORD
        })
        assert resp.status_code == 200, f"Receptionist login failed: {resp.text}"
        return session

    def test_admin_can_create_role(self, admin_session):
        """Admin (legacy admin) can create roles - bypasses permission check"""
        resp = admin_session.post(f"{BASE_URL}/api/rbac/roles", json={
            "key": "test_iter146_admin_create",
            "display_name": "Test Role by Admin",
            "permissions": ["view_bookings"]
        })
        assert resp.status_code == 200, f"Admin should be able to create role: {resp.text}"
        data = resp.json()
        assert data["key"] == "test_iter146_admin_create"
        
        # Cleanup
        admin_session.delete(f"{BASE_URL}/api/rbac/roles/{data['id']}")
        print("✓ Admin can create roles (legacy admin bypass)")

    def test_receptionist_cannot_create_role(self, receptionist_session):
        """Receptionist without create_roles permission gets 403"""
        resp = receptionist_session.post(f"{BASE_URL}/api/rbac/roles", json={
            "key": "test_iter146_sarah_create",
            "display_name": "Test Role by Sarah",
            "permissions": ["view_bookings"]
        })
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "Missing permission" in data.get("detail", ""), f"Expected 'Missing permission' in detail, got: {data}"
        assert "create_roles" in data.get("detail", ""), f"Expected 'create_roles' in detail, got: {data}"
        print("✓ Receptionist blocked from creating roles (403 with 'Missing permission: create_roles')")

    def test_admin_can_update_role(self, admin_session):
        """Admin can update roles"""
        # First create a role
        create_resp = admin_session.post(f"{BASE_URL}/api/rbac/roles", json={
            "key": "test_iter146_update",
            "display_name": "Test Update Role",
            "permissions": ["view_bookings"]
        })
        assert create_resp.status_code == 200
        role_id = create_resp.json()["id"]
        
        # Update it
        update_resp = admin_session.put(f"{BASE_URL}/api/rbac/roles/{role_id}", json={
            "display_name": "Updated Display Name"
        })
        assert update_resp.status_code == 200, f"Admin should be able to update role: {update_resp.text}"
        
        # Cleanup
        admin_session.delete(f"{BASE_URL}/api/rbac/roles/{role_id}")
        print("✓ Admin can update roles")

    def test_receptionist_cannot_update_role(self, receptionist_session, admin_session):
        """Receptionist without edit_roles permission gets 403 on PUT"""
        # Admin creates a role
        create_resp = admin_session.post(f"{BASE_URL}/api/rbac/roles", json={
            "key": "test_iter146_sarah_update",
            "display_name": "Test Role for Sarah Update",
            "permissions": ["view_bookings"]
        })
        assert create_resp.status_code == 200
        role_id = create_resp.json()["id"]
        
        # Receptionist tries to update
        update_resp = receptionist_session.put(f"{BASE_URL}/api/rbac/roles/{role_id}", json={
            "display_name": "Sarah's Update"
        })
        assert update_resp.status_code == 403, f"Expected 403, got {update_resp.status_code}: {update_resp.text}"
        data = update_resp.json()
        assert "Missing permission" in data.get("detail", "")
        assert "edit_roles" in data.get("detail", "")
        
        # Cleanup
        admin_session.delete(f"{BASE_URL}/api/rbac/roles/{role_id}")
        print("✓ Receptionist blocked from updating roles (403 with 'Missing permission: edit_roles')")

    def test_admin_can_delete_role(self, admin_session):
        """Admin can delete roles"""
        # Create a role
        create_resp = admin_session.post(f"{BASE_URL}/api/rbac/roles", json={
            "key": "test_iter146_delete",
            "display_name": "Test Delete Role",
            "permissions": []
        })
        assert create_resp.status_code == 200
        role_id = create_resp.json()["id"]
        
        # Delete it
        delete_resp = admin_session.delete(f"{BASE_URL}/api/rbac/roles/{role_id}")
        assert delete_resp.status_code == 200, f"Admin should be able to delete role: {delete_resp.text}"
        print("✓ Admin can delete roles")

    def test_receptionist_cannot_delete_role(self, receptionist_session, admin_session):
        """Receptionist without delete_roles permission gets 403 on DELETE"""
        # Admin creates a role
        create_resp = admin_session.post(f"{BASE_URL}/api/rbac/roles", json={
            "key": "test_iter146_sarah_delete",
            "display_name": "Test Role for Sarah Delete",
            "permissions": []
        })
        assert create_resp.status_code == 200
        role_id = create_resp.json()["id"]
        
        # Receptionist tries to delete
        delete_resp = receptionist_session.delete(f"{BASE_URL}/api/rbac/roles/{role_id}")
        assert delete_resp.status_code == 403, f"Expected 403, got {delete_resp.status_code}: {delete_resp.text}"
        data = delete_resp.json()
        assert "Missing permission" in data.get("detail", "")
        assert "delete_roles" in data.get("detail", "")
        
        # Cleanup
        admin_session.delete(f"{BASE_URL}/api/rbac/roles/{role_id}")
        print("✓ Receptionist blocked from deleting roles (403 with 'Missing permission: delete_roles')")

    def test_admin_can_clone_role(self, admin_session):
        """Admin can clone roles (requires create_roles)"""
        # Create a role
        create_resp = admin_session.post(f"{BASE_URL}/api/rbac/roles", json={
            "key": "test_iter146_clone_src",
            "display_name": "Clone Source",
            "permissions": ["view_bookings"]
        })
        assert create_resp.status_code == 200
        role_id = create_resp.json()["id"]
        
        # Clone it
        clone_resp = admin_session.post(f"{BASE_URL}/api/rbac/roles/{role_id}/clone", json={
            "new_key": "test_iter146_clone_dst",
            "display_name": "Clone Destination"
        })
        assert clone_resp.status_code == 200, f"Admin should be able to clone role: {clone_resp.text}"
        clone_id = clone_resp.json()["id"]
        
        # Cleanup
        admin_session.delete(f"{BASE_URL}/api/rbac/roles/{clone_id}")
        admin_session.delete(f"{BASE_URL}/api/rbac/roles/{role_id}")
        print("✓ Admin can clone roles")

    def test_receptionist_cannot_clone_role(self, receptionist_session, admin_session):
        """Receptionist without create_roles permission gets 403 on clone"""
        # Admin creates a role
        create_resp = admin_session.post(f"{BASE_URL}/api/rbac/roles", json={
            "key": "test_iter146_sarah_clone",
            "display_name": "Test Role for Sarah Clone",
            "permissions": []
        })
        assert create_resp.status_code == 200
        role_id = create_resp.json()["id"]
        
        # Receptionist tries to clone
        clone_resp = receptionist_session.post(f"{BASE_URL}/api/rbac/roles/{role_id}/clone", json={
            "new_key": "test_iter146_sarah_clone_dst",
            "display_name": "Sarah's Clone"
        })
        assert clone_resp.status_code == 403, f"Expected 403, got {clone_resp.status_code}: {clone_resp.text}"
        data = clone_resp.json()
        assert "Missing permission" in data.get("detail", "")
        assert "create_roles" in data.get("detail", "")
        
        # Cleanup
        admin_session.delete(f"{BASE_URL}/api/rbac/roles/{role_id}")
        print("✓ Receptionist blocked from cloning roles (403 with 'Missing permission: create_roles')")


class TestLegacyEndpointsRegression:
    """Verify legacy endpoints using require_roles still work"""

    @pytest.fixture(scope="class")
    def admin_session(self):
        """Login as admin and return session"""
        session = requests.Session()
        resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert resp.status_code == 200, f"Admin login failed: {resp.text}"
        return session

    def test_rbac_catalog_still_works(self, admin_session):
        """GET /api/rbac/catalog still works (uses get_current_user)"""
        resp = admin_session.get(f"{BASE_URL}/api/rbac/catalog")
        assert resp.status_code == 200, f"Catalog should work: {resp.text}"
        data = resp.json()
        assert "catalog" in data
        assert "templates" in data
        print("✓ GET /api/rbac/catalog works")

    def test_rbac_roles_list_still_works(self, admin_session):
        """GET /api/rbac/roles still works (uses require_roles)"""
        resp = admin_session.get(f"{BASE_URL}/api/rbac/roles")
        assert resp.status_code == 200, f"Roles list should work: {resp.text}"
        data = resp.json()
        assert "roles" in data
        print("✓ GET /api/rbac/roles works")

    def test_bookings_endpoint_still_works(self, admin_session):
        """GET /api/bookings still works (legacy endpoint)"""
        resp = admin_session.get(f"{BASE_URL}/api/bookings")
        assert resp.status_code == 200, f"Bookings should work: {resp.text}"
        print("✓ GET /api/bookings works (legacy endpoint)")

    def test_users_endpoint_still_works(self, admin_session):
        """GET /api/users still works (legacy endpoint)"""
        resp = admin_session.get(f"{BASE_URL}/api/users")
        assert resp.status_code == 200, f"Users should work: {resp.text}"
        print("✓ GET /api/users works (legacy endpoint)")


class TestReceptionistPermissionDetails:
    """Detailed tests for receptionist's specific permissions"""

    @pytest.fixture(scope="class")
    def receptionist_session(self):
        """Login as receptionist (sarah) and return session"""
        session = requests.Session()
        resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": RECEPTIONIST_EMAIL,
            "password": RECEPTIONIST_PASSWORD
        })
        assert resp.status_code == 200, f"Receptionist login failed: {resp.text}"
        return session

    def test_receptionist_has_bookings_view(self, receptionist_session):
        """Receptionist should have bookings_view permission"""
        resp = receptionist_session.get(f"{BASE_URL}/api/rbac/me/permissions")
        assert resp.status_code == 200
        data = resp.json()
        
        # Check for bookings-related permissions
        perms = set(data["permissions"])
        # Receptionist template should include view_bookings or bookings_view
        has_booking_perm = "view_bookings" in perms or "bookings_view" in perms
        assert has_booking_perm, f"Receptionist should have booking view permission. Perms: {perms}"
        print("✓ Receptionist has booking view permission")

    def test_receptionist_lacks_payroll_permission(self, receptionist_session):
        """Receptionist should NOT have payroll permissions"""
        resp = receptionist_session.get(f"{BASE_URL}/api/rbac/me/permissions")
        assert resp.status_code == 200
        data = resp.json()
        
        perms = set(data["permissions"])
        menu_perms = set(data["menu_permissions"])
        
        # Receptionist should NOT have finance/payroll permissions
        assert "finance_payroll_runs_view" not in menu_perms, "Receptionist should not have payroll menu permission"
        assert "approve_payroll_runs" not in perms, "Receptionist should not have approve_payroll_runs"
        print("✓ Receptionist lacks payroll permissions (as expected)")

    def test_receptionist_lacks_roles_permission(self, receptionist_session):
        """Receptionist should NOT have roles management permissions"""
        resp = receptionist_session.get(f"{BASE_URL}/api/rbac/me/permissions")
        assert resp.status_code == 200
        data = resp.json()
        
        perms = set(data["permissions"])
        menu_perms = set(data["menu_permissions"])
        
        # Receptionist should NOT have roles permissions
        assert "create_roles" not in perms, "Receptionist should not have create_roles"
        assert "edit_roles" not in perms, "Receptionist should not have edit_roles"
        assert "delete_roles" not in perms, "Receptionist should not have delete_roles"
        assert "settings_roles_view" not in menu_perms, "Receptionist should not have roles menu permission"
        print("✓ Receptionist lacks roles management permissions (as expected)")


# Cleanup fixture to remove any test roles that might have been left behind
@pytest.fixture(scope="session", autouse=True)
def cleanup_test_roles():
    """Cleanup test roles after all tests complete"""
    yield
    # After tests, cleanup any leftover test roles
    session = requests.Session()
    resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if resp.status_code == 200:
        roles_resp = session.get(f"{BASE_URL}/api/rbac/roles")
        if roles_resp.status_code == 200:
            for role in roles_resp.json().get("roles", []):
                if role.get("key", "").startswith("test_iter146_"):
                    session.delete(f"{BASE_URL}/api/rbac/roles/{role['id']}")
                    print(f"Cleaned up test role: {role['key']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
