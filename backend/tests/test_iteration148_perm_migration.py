"""
Iteration 148 - Permission Migration Testing
Tests:
1. POST /api/auth/register requires create_users permission (admin bypass, Sarah 403)
2. PUT /api/users/{id} requires edit_users permission
3. DELETE /api/users/{id} requires delete_users permission
4. POST /api/properties requires create_branches permission
5. PUT /api/properties/{id} requires edit_branches permission
6. DELETE /api/properties/{id} requires delete_branches permission
7. POST /api/payroll/runs/{pid}/{rid}/approve requires approve_payroll_runs
8. POST /api/payroll/runs/{pid}/{rid}/mark-paid requires approve_payroll_runs
9. DELETE /api/payroll/runs/{pid}/{rid} requires delete_payroll_runs
10. Non-migrated endpoints (bug-tracker, arrivals, bookings, etc.) still work with require_roles
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
RECEPTIONIST_EMAIL = "sarah@hotel.test"
RECEPTIONIST_PASSWORD = "StaffP@ss1"


class TestAuthSetup:
    """Setup and verify authentication works"""
    
    @pytest.fixture(scope="class")
    def admin_session(self):
        """Get admin session with cookies"""
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        return session
    
    @pytest.fixture(scope="class")
    def receptionist_session(self):
        """Get receptionist (Sarah) session with cookies"""
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": RECEPTIONIST_EMAIL,
            "password": RECEPTIONIST_PASSWORD
        })
        assert response.status_code == 200, f"Receptionist login failed: {response.text}"
        return session
    
    def test_admin_login(self, admin_session):
        """Verify admin can login"""
        response = admin_session.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "admin"
        print(f"✓ Admin login verified: {data['email']}")
    
    def test_receptionist_login(self, receptionist_session):
        """Verify receptionist can login"""
        response = receptionist_session.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "receptionist"
        print(f"✓ Receptionist login verified: {data['email']}")


class TestUserManagementPermissions:
    """Test user management endpoints with require_perm"""
    
    @pytest.fixture(scope="class")
    def admin_session(self):
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        return session
    
    @pytest.fixture(scope="class")
    def receptionist_session(self):
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": RECEPTIONIST_EMAIL,
            "password": RECEPTIONIST_PASSWORD
        })
        assert response.status_code == 200
        return session
    
    def test_register_admin_bypass(self, admin_session):
        """Admin can register new users (bypass)"""
        test_email = f"test_perm_{uuid.uuid4().hex[:8]}@test.com"
        response = admin_session.post(f"{BASE_URL}/api/auth/register", json={
            "email": test_email,
            "password": "TestPass123!",
            "name": "Test Perm User",
            "role": "receptionist",
            "department": "front_desk"
        })
        assert response.status_code == 200, f"Admin register failed: {response.text}"
        data = response.json()
        assert data["email"] == test_email
        print(f"✓ Admin can register users (bypass): {test_email}")
        # Cleanup - delete the test user
        user_id = data.get("id")
        if user_id:
            admin_session.delete(f"{BASE_URL}/api/users/{user_id}")
    
    def test_register_receptionist_403(self, receptionist_session):
        """Receptionist gets 403 when trying to register users"""
        test_email = f"test_blocked_{uuid.uuid4().hex[:8]}@test.com"
        response = receptionist_session.post(f"{BASE_URL}/api/auth/register", json={
            "email": test_email,
            "password": "TestPass123!",
            "name": "Blocked User",
            "role": "receptionist",
            "department": "front_desk"
        })
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        data = response.json()
        assert "Missing permission" in data.get("detail", "") or "create_users" in data.get("detail", "")
        print(f"✓ Receptionist blocked from register (403): {data.get('detail')}")
    
    def test_update_user_admin_bypass(self, admin_session):
        """Admin can update users (bypass)"""
        # First get a user to update
        users_resp = admin_session.get(f"{BASE_URL}/api/users")
        assert users_resp.status_code == 200
        users = users_resp.json()
        # Find a non-admin user to update
        target_user = next((u for u in users if u.get("role") != "admin"), None)
        if target_user:
            response = admin_session.put(f"{BASE_URL}/api/users/{target_user['id']}", json={
                "name": target_user.get("name", "Updated")  # No actual change
            })
            assert response.status_code == 200, f"Admin update user failed: {response.text}"
            print(f"✓ Admin can update users (bypass)")
        else:
            print("⚠ No non-admin user found to test update")
    
    def test_update_user_receptionist_403(self, receptionist_session, admin_session):
        """Receptionist gets 403 when trying to update users"""
        # Get a user ID to try updating
        users_resp = admin_session.get(f"{BASE_URL}/api/users")
        users = users_resp.json()
        target_user = next((u for u in users if u.get("role") != "admin"), None)
        if target_user:
            response = receptionist_session.put(f"{BASE_URL}/api/users/{target_user['id']}", json={
                "name": "Blocked Update"
            })
            assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
            data = response.json()
            assert "Missing permission" in data.get("detail", "") or "edit_users" in data.get("detail", "")
            print(f"✓ Receptionist blocked from update user (403): {data.get('detail')}")
    
    def test_delete_user_receptionist_403(self, receptionist_session, admin_session):
        """Receptionist gets 403 when trying to delete users"""
        # Create a test user to try deleting
        test_email = f"test_del_{uuid.uuid4().hex[:8]}@test.com"
        create_resp = admin_session.post(f"{BASE_URL}/api/auth/register", json={
            "email": test_email,
            "password": "TestPass123!",
            "name": "Delete Test",
            "role": "receptionist",
            "department": "front_desk"
        })
        if create_resp.status_code == 200:
            user_id = create_resp.json().get("id")
            # Try to delete as receptionist
            response = receptionist_session.delete(f"{BASE_URL}/api/users/{user_id}")
            assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
            data = response.json()
            assert "Missing permission" in data.get("detail", "") or "delete_users" in data.get("detail", "")
            print(f"✓ Receptionist blocked from delete user (403): {data.get('detail')}")
            # Cleanup
            admin_session.delete(f"{BASE_URL}/api/users/{user_id}")


class TestPropertyPermissions:
    """Test property management endpoints with require_perm"""
    
    @pytest.fixture(scope="class")
    def admin_session(self):
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        return session
    
    @pytest.fixture(scope="class")
    def receptionist_session(self):
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": RECEPTIONIST_EMAIL,
            "password": RECEPTIONIST_PASSWORD
        })
        assert response.status_code == 200
        return session
    
    def test_create_property_admin_bypass(self, admin_session):
        """Admin can create properties (bypass)"""
        test_name = f"Test Property {uuid.uuid4().hex[:8]}"
        response = admin_session.post(f"{BASE_URL}/api/properties", json={
            "name": test_name,
            "address": "123 Test St",
            "city": "Test City",
            "country": "UK",
            "property_type": "hotel"
        })
        assert response.status_code == 200, f"Admin create property failed: {response.text}"
        data = response.json()
        assert data["name"] == test_name
        print(f"✓ Admin can create properties (bypass): {test_name}")
        # Cleanup
        prop_id = data.get("id")
        if prop_id:
            admin_session.delete(f"{BASE_URL}/api/properties/{prop_id}")
    
    def test_create_property_receptionist_403(self, receptionist_session):
        """Receptionist gets 403 when trying to create properties"""
        response = receptionist_session.post(f"{BASE_URL}/api/properties", json={
            "name": "Blocked Property",
            "address": "123 Blocked St",
            "city": "Blocked City",
            "country": "UK",
            "property_type": "hotel"
        })
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        data = response.json()
        assert "Missing permission" in data.get("detail", "") or "create_branches" in data.get("detail", "")
        print(f"✓ Receptionist blocked from create property (403): {data.get('detail')}")
    
    def test_update_property_receptionist_403(self, receptionist_session, admin_session):
        """Receptionist gets 403 when trying to update properties"""
        # Get existing properties
        props_resp = admin_session.get(f"{BASE_URL}/api/properties")
        if props_resp.status_code == 200:
            props = props_resp.json()
            if props:
                prop_id = props[0].get("id")
                response = receptionist_session.put(f"{BASE_URL}/api/properties/{prop_id}", json={
                    "name": "Blocked Update"
                })
                assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
                data = response.json()
                assert "Missing permission" in data.get("detail", "") or "edit_branches" in data.get("detail", "")
                print(f"✓ Receptionist blocked from update property (403): {data.get('detail')}")
    
    def test_delete_property_receptionist_403(self, receptionist_session, admin_session):
        """Receptionist gets 403 when trying to delete properties"""
        # Create a test property to try deleting
        test_name = f"Test Del Prop {uuid.uuid4().hex[:8]}"
        create_resp = admin_session.post(f"{BASE_URL}/api/properties", json={
            "name": test_name,
            "address": "123 Del St",
            "city": "Del City",
            "country": "UK",
            "property_type": "hotel"
        })
        if create_resp.status_code == 200:
            prop_id = create_resp.json().get("id")
            # Try to delete as receptionist
            response = receptionist_session.delete(f"{BASE_URL}/api/properties/{prop_id}")
            assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
            data = response.json()
            assert "Missing permission" in data.get("detail", "") or "delete_branches" in data.get("detail", "")
            print(f"✓ Receptionist blocked from delete property (403): {data.get('detail')}")
            # Cleanup
            admin_session.delete(f"{BASE_URL}/api/properties/{prop_id}")


class TestPayrollPermissions:
    """Test payroll endpoints with require_perm"""
    
    @pytest.fixture(scope="class")
    def admin_session(self):
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        return session
    
    @pytest.fixture(scope="class")
    def receptionist_session(self):
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": RECEPTIONIST_EMAIL,
            "password": RECEPTIONIST_PASSWORD
        })
        assert response.status_code == 200
        return session
    
    def test_approve_run_admin_bypass(self, admin_session):
        """Admin can approve payroll runs (bypass)"""
        # First create a payroll run
        create_resp = admin_session.post(f"{BASE_URL}/api/payroll/runs/default", json={
            "year": 2025,
            "month": 1
        })
        if create_resp.status_code == 200:
            run_id = create_resp.json().get("id")
            # Approve it
            response = admin_session.post(f"{BASE_URL}/api/payroll/runs/default/{run_id}/approve")
            assert response.status_code == 200, f"Admin approve run failed: {response.text}"
            print(f"✓ Admin can approve payroll runs (bypass)")
            # Cleanup
            admin_session.delete(f"{BASE_URL}/api/payroll/runs/default/{run_id}")
        elif create_resp.status_code == 400 and "already exists" in create_resp.text:
            # Run already exists, try to get it
            runs_resp = admin_session.get(f"{BASE_URL}/api/payroll/runs/default")
            if runs_resp.status_code == 200:
                runs = runs_resp.json().get("runs", [])
                jan_run = next((r for r in runs if r.get("year") == 2025 and r.get("month") == 1), None)
                if jan_run:
                    print(f"✓ Admin payroll run already exists, skipping create test")
    
    def test_approve_run_receptionist_403(self, receptionist_session, admin_session):
        """Receptionist gets 403 when trying to approve payroll runs"""
        # Get existing runs
        runs_resp = admin_session.get(f"{BASE_URL}/api/payroll/runs/default")
        if runs_resp.status_code == 200:
            runs = runs_resp.json().get("runs", [])
            if runs:
                run_id = runs[0].get("id")
                response = receptionist_session.post(f"{BASE_URL}/api/payroll/runs/default/{run_id}/approve")
                assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
                data = response.json()
                assert "Missing permission" in data.get("detail", "") or "approve_payroll_runs" in data.get("detail", "")
                print(f"✓ Receptionist blocked from approve payroll run (403): {data.get('detail')}")
            else:
                # Create a run to test
                create_resp = admin_session.post(f"{BASE_URL}/api/payroll/runs/default", json={
                    "year": 2025,
                    "month": 2
                })
                if create_resp.status_code == 200:
                    run_id = create_resp.json().get("id")
                    response = receptionist_session.post(f"{BASE_URL}/api/payroll/runs/default/{run_id}/approve")
                    assert response.status_code == 403
                    print(f"✓ Receptionist blocked from approve payroll run (403)")
                    admin_session.delete(f"{BASE_URL}/api/payroll/runs/default/{run_id}")
    
    def test_mark_paid_receptionist_403(self, receptionist_session, admin_session):
        """Receptionist gets 403 when trying to mark payroll runs as paid"""
        runs_resp = admin_session.get(f"{BASE_URL}/api/payroll/runs/default")
        if runs_resp.status_code == 200:
            runs = runs_resp.json().get("runs", [])
            if runs:
                run_id = runs[0].get("id")
                response = receptionist_session.post(f"{BASE_URL}/api/payroll/runs/default/{run_id}/mark-paid")
                assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
                data = response.json()
                assert "Missing permission" in data.get("detail", "") or "approve_payroll_runs" in data.get("detail", "")
                print(f"✓ Receptionist blocked from mark-paid (403): {data.get('detail')}")
    
    def test_delete_run_receptionist_403(self, receptionist_session, admin_session):
        """Receptionist gets 403 when trying to delete payroll runs"""
        # Create a test run
        create_resp = admin_session.post(f"{BASE_URL}/api/payroll/runs/default", json={
            "year": 2025,
            "month": 3
        })
        if create_resp.status_code == 200:
            run_id = create_resp.json().get("id")
            response = receptionist_session.delete(f"{BASE_URL}/api/payroll/runs/default/{run_id}")
            assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
            data = response.json()
            assert "Missing permission" in data.get("detail", "") or "delete_payroll_runs" in data.get("detail", "")
            print(f"✓ Receptionist blocked from delete payroll run (403): {data.get('detail')}")
            # Cleanup
            admin_session.delete(f"{BASE_URL}/api/payroll/runs/default/{run_id}")


class TestNonMigratedEndpoints:
    """Test that non-migrated endpoints still work with require_roles (no regression)"""
    
    @pytest.fixture(scope="class")
    def admin_session(self):
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        return session
    
    @pytest.fixture(scope="class")
    def receptionist_session(self):
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": RECEPTIONIST_EMAIL,
            "password": RECEPTIONIST_PASSWORD
        })
        assert response.status_code == 200
        return session
    
    def test_bug_tracker_list(self, admin_session):
        """Bug tracker list still works (require_roles)"""
        response = admin_session.get(f"{BASE_URL}/api/bugs")
        assert response.status_code == 200, f"Bug tracker list failed: {response.text}"
        print(f"✓ Bug tracker list works (require_roles)")
    
    def test_arrivals_list(self, admin_session):
        """Arrivals list still works"""
        response = admin_session.get(f"{BASE_URL}/api/arrivals/default")
        # May return 200 or empty list
        assert response.status_code in [200, 404], f"Arrivals list failed: {response.text}"
        print(f"✓ Arrivals endpoint works")
    
    def test_bookings_list(self, admin_session):
        """Bookings list still works"""
        response = admin_session.get(f"{BASE_URL}/api/bookings")
        assert response.status_code == 200, f"Bookings list failed: {response.text}"
        print(f"✓ Bookings list works")
    
    def test_channel_manager_connections(self, admin_session):
        """Channel manager connections still works"""
        response = admin_session.get(f"{BASE_URL}/api/channel-manager/connections")
        assert response.status_code == 200, f"Channel manager failed: {response.text}"
        print(f"✓ Channel manager connections works")
    
    def test_accounting_income(self, admin_session):
        """Accounting income still works (require_roles)"""
        response = admin_session.get(f"{BASE_URL}/api/accounting/income/default")
        assert response.status_code == 200, f"Accounting income failed: {response.text}"
        print(f"✓ Accounting income works (require_roles)")
    
    def test_payroll_earnings(self, admin_session):
        """Payroll earnings still works (require_roles)"""
        response = admin_session.get(f"{BASE_URL}/api/payroll/earnings/default")
        assert response.status_code == 200, f"Payroll earnings failed: {response.text}"
        print(f"✓ Payroll earnings works (require_roles)")
    
    def test_payroll_adjustments(self, admin_session):
        """Payroll adjustments still works (require_roles)"""
        response = admin_session.get(f"{BASE_URL}/api/payroll/adjustments/default")
        assert response.status_code == 200, f"Payroll adjustments failed: {response.text}"
        print(f"✓ Payroll adjustments works (require_roles)")


class TestReceptionistAllowedEndpoints:
    """Test endpoints that receptionist SHOULD be able to access"""
    
    @pytest.fixture(scope="class")
    def receptionist_session(self):
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": RECEPTIONIST_EMAIL,
            "password": RECEPTIONIST_PASSWORD
        })
        assert response.status_code == 200
        return session
    
    def test_receptionist_can_view_bookings(self, receptionist_session):
        """Receptionist can view bookings"""
        response = receptionist_session.get(f"{BASE_URL}/api/bookings")
        assert response.status_code == 200, f"Receptionist bookings failed: {response.text}"
        print(f"✓ Receptionist can view bookings")
    
    def test_receptionist_can_view_reviews(self, receptionist_session):
        """Receptionist can view reviews"""
        response = receptionist_session.get(f"{BASE_URL}/api/reviews")
        assert response.status_code == 200, f"Receptionist reviews failed: {response.text}"
        print(f"✓ Receptionist can view reviews")
    
    def test_receptionist_can_view_properties(self, receptionist_session):
        """Receptionist can view properties (GET is not gated)"""
        response = receptionist_session.get(f"{BASE_URL}/api/properties")
        assert response.status_code == 200, f"Receptionist properties failed: {response.text}"
        print(f"✓ Receptionist can view properties")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
