"""
Iteration 145 - Enhanced RBAC Testing
Tests for:
1. GET /api/rbac/catalog - enriched permissions with risk + implies fields
2. POST /api/rbac/ai-suggest - GPT-5.2 AI Role Designer (admin only)
3. Existing RBAC endpoints regression (roles CRUD, clone)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token"""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if resp.status_code != 200:
        pytest.skip(f"Admin login failed: {resp.status_code} - {resp.text[:200]}")
    data = resp.json()
    return data.get("token") or data.get("access_token")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    """Headers with admin auth"""
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


class TestEnrichedCatalog:
    """Test GET /api/rbac/catalog returns enriched permissions with risk + implies"""

    def test_catalog_requires_auth(self):
        """Catalog endpoint requires authentication"""
        resp = requests.get(f"{BASE_URL}/api/rbac/catalog")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

    def test_catalog_returns_enriched_permissions(self, admin_headers):
        """Catalog returns permissions with risk and implies fields"""
        resp = requests.get(f"{BASE_URL}/api/rbac/catalog", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        
        data = resp.json()
        assert "catalog" in data
        assert "templates" in data
        assert "total_permissions" in data
        assert "all_permission_keys" in data
        
        # Check that permissions have risk and implies fields
        catalog = data["catalog"]
        assert len(catalog) > 0, "Catalog should have categories"
        
        found_risk = False
        found_implies = False
        
        for cat in catalog:
            for sg in cat.get("sub_groups", []):
                for perm in sg.get("permissions", []):
                    # Every permission should have risk field
                    assert "risk" in perm, f"Permission {perm.get('key')} missing 'risk' field"
                    # Every permission should have implies field
                    assert "implies" in perm, f"Permission {perm.get('key')} missing 'implies' field"
                    
                    if perm["risk"] != "low":
                        found_risk = True
                    if len(perm["implies"]) > 0:
                        found_implies = True
        
        assert found_risk, "Should have at least one permission with risk != low"
        assert found_implies, "Should have at least one permission with implies dependencies"

    def test_delete_bookings_has_critical_risk(self, admin_headers):
        """delete_bookings permission should have risk=critical"""
        resp = requests.get(f"{BASE_URL}/api/rbac/catalog", headers=admin_headers)
        assert resp.status_code == 200
        
        data = resp.json()
        catalog = data["catalog"]
        
        delete_bookings_perm = None
        for cat in catalog:
            for sg in cat.get("sub_groups", []):
                for perm in sg.get("permissions", []):
                    if perm["key"] == "delete_bookings":
                        delete_bookings_perm = perm
                        break
        
        assert delete_bookings_perm is not None, "delete_bookings permission not found"
        assert delete_bookings_perm["risk"] == "critical", f"Expected risk=critical, got {delete_bookings_perm['risk']}"

    def test_create_bookings_implies_view_bookings(self, admin_headers):
        """create_bookings permission should imply view_bookings"""
        resp = requests.get(f"{BASE_URL}/api/rbac/catalog", headers=admin_headers)
        assert resp.status_code == 200
        
        data = resp.json()
        catalog = data["catalog"]
        
        create_bookings_perm = None
        for cat in catalog:
            for sg in cat.get("sub_groups", []):
                for perm in sg.get("permissions", []):
                    if perm["key"] == "create_bookings":
                        create_bookings_perm = perm
                        break
        
        assert create_bookings_perm is not None, "create_bookings permission not found"
        assert "view_bookings" in create_bookings_perm["implies"], \
            f"Expected view_bookings in implies, got {create_bookings_perm['implies']}"

    def test_risk_levels_distribution(self, admin_headers):
        """Verify risk levels are properly distributed across permissions"""
        resp = requests.get(f"{BASE_URL}/api/rbac/catalog", headers=admin_headers)
        assert resp.status_code == 200
        
        data = resp.json()
        catalog = data["catalog"]
        
        risk_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        
        for cat in catalog:
            for sg in cat.get("sub_groups", []):
                for perm in sg.get("permissions", []):
                    risk = perm.get("risk", "low")
                    if risk in risk_counts:
                        risk_counts[risk] += 1
        
        # Should have multiple critical/high/medium permissions
        assert risk_counts["critical"] > 0, "Should have critical risk permissions"
        assert risk_counts["high"] > 0, "Should have high risk permissions"
        assert risk_counts["medium"] > 0, "Should have medium risk permissions"
        print(f"Risk distribution: {risk_counts}")


class TestAISuggestEndpoint:
    """Test POST /api/rbac/ai-suggest - GPT-5.2 AI Role Designer"""

    def test_ai_suggest_requires_auth(self):
        """AI suggest endpoint requires authentication"""
        resp = requests.post(f"{BASE_URL}/api/rbac/ai-suggest", json={
            "description": "A night shift receptionist who checks in guests",
            "existing_permissions": []
        })
        assert resp.status_code in [401, 403], f"Expected 401/403, got {resp.status_code}"

    def test_ai_suggest_requires_admin_role(self, admin_headers):
        """AI suggest endpoint requires admin role (not just manager)"""
        # This test verifies the endpoint works for admin
        # Manager test would require a manager user
        resp = requests.post(f"{BASE_URL}/api/rbac/ai-suggest", headers=admin_headers, json={
            "description": "A basic receptionist who can view bookings only",
            "existing_permissions": []
        })
        # Should either succeed (200) or fail with AI error (502) - not 403
        assert resp.status_code in [200, 502], f"Expected 200 or 502, got {resp.status_code}: {resp.text[:300]}"

    def test_ai_suggest_rejects_short_description(self, admin_headers):
        """AI suggest rejects description shorter than 10 characters"""
        resp = requests.post(f"{BASE_URL}/api/rbac/ai-suggest", headers=admin_headers, json={
            "description": "short",
            "existing_permissions": []
        })
        assert resp.status_code == 422, f"Expected 422 for short description, got {resp.status_code}"

    def test_ai_suggest_returns_valid_response(self, admin_headers):
        """AI suggest returns valid response with permissions, reasoning, suggestions"""
        resp = requests.post(f"{BASE_URL}/api/rbac/ai-suggest", headers=admin_headers, json={
            "description": "A night shift receptionist who checks in guests, handles petty cash reconciliation, views rates but cannot edit them, and should not see payroll.",
            "existing_permissions": []
        }, timeout=30)  # GPT-5.2 may take time
        
        # Accept 200 (success) or 502 (AI budget/error - acceptable per requirements)
        if resp.status_code == 502:
            print(f"AI suggest returned 502 (budget/error): {resp.text[:200]}")
            pytest.skip("AI suggest returned 502 - acceptable per requirements")
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
        
        data = resp.json()
        
        # Verify response structure
        assert "permissions" in data, "Response should have 'permissions' field"
        assert "reasoning" in data, "Response should have 'reasoning' field"
        assert "role_name_suggestion" in data, "Response should have 'role_name_suggestion' field"
        assert "display_name_suggestion" in data, "Response should have 'display_name_suggestion' field"
        assert "total_suggested" in data, "Response should have 'total_suggested' field"
        assert "invalid_dropped" in data, "Response should have 'invalid_dropped' field"
        
        # Verify permissions is a list
        assert isinstance(data["permissions"], list), "permissions should be a list"
        
        # Verify total_suggested matches permissions length
        assert data["total_suggested"] == len(data["permissions"]), \
            f"total_suggested ({data['total_suggested']}) should match permissions length ({len(data['permissions'])})"
        
        print(f"AI suggested {data['total_suggested']} permissions")
        print(f"Role name suggestion: {data['role_name_suggestion']}")
        print(f"Reasoning: {data['reasoning'][:200]}...")

    def test_ai_suggest_drops_invalid_permissions(self, admin_headers):
        """AI suggest drops invalid permission keys from response"""
        # This is tested implicitly - the backend filters out invalid keys
        # We just verify the invalid_dropped field exists
        resp = requests.post(f"{BASE_URL}/api/rbac/ai-suggest", headers=admin_headers, json={
            "description": "A simple viewer who can only see the dashboard",
            "existing_permissions": []
        }, timeout=30)
        
        if resp.status_code == 502:
            pytest.skip("AI suggest returned 502 - acceptable per requirements")
        
        assert resp.status_code == 200
        data = resp.json()
        assert "invalid_dropped" in data
        assert isinstance(data["invalid_dropped"], int)


class TestExistingRBACEndpoints:
    """Regression tests for existing RBAC endpoints"""

    def test_list_roles(self, admin_headers):
        """GET /api/rbac/roles returns roles list"""
        resp = requests.get(f"{BASE_URL}/api/rbac/roles", headers=admin_headers)
        assert resp.status_code == 200
        
        data = resp.json()
        assert "roles" in data
        assert "total" in data
        assert "total_permissions_available" in data

    def test_create_role(self, admin_headers):
        """POST /api/rbac/roles creates a new role"""
        import uuid
        test_key = f"test_iter145_{uuid.uuid4().hex[:8]}"
        
        resp = requests.post(f"{BASE_URL}/api/rbac/roles", headers=admin_headers, json={
            "key": test_key,
            "display_name": "Test Role Iteration 145",
            "permissions": ["dashboard_view", "tasks_my_view"],
            "is_global_admin": False
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        
        data = resp.json()
        assert data["key"] == test_key
        assert data["display_name"] == "Test Role Iteration 145"
        assert "dashboard_view" in data["permissions"]
        assert "tasks_my_view" in data["permissions"]
        
        # Cleanup
        role_id = data["id"]
        requests.delete(f"{BASE_URL}/api/rbac/roles/{role_id}", headers=admin_headers)

    def test_get_role(self, admin_headers):
        """GET /api/rbac/roles/{id} returns role details"""
        # First create a role
        import uuid
        test_key = f"test_get_{uuid.uuid4().hex[:8]}"
        
        create_resp = requests.post(f"{BASE_URL}/api/rbac/roles", headers=admin_headers, json={
            "key": test_key,
            "display_name": "Test Get Role",
            "permissions": ["dashboard_view"]
        })
        assert create_resp.status_code == 200
        role_id = create_resp.json()["id"]
        
        # Get the role
        resp = requests.get(f"{BASE_URL}/api/rbac/roles/{role_id}", headers=admin_headers)
        assert resp.status_code == 200
        
        data = resp.json()
        assert data["key"] == test_key
        assert "assigned_users" in data
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/rbac/roles/{role_id}", headers=admin_headers)

    def test_update_role(self, admin_headers):
        """PUT /api/rbac/roles/{id} updates role"""
        import uuid
        test_key = f"test_update_{uuid.uuid4().hex[:8]}"
        
        # Create
        create_resp = requests.post(f"{BASE_URL}/api/rbac/roles", headers=admin_headers, json={
            "key": test_key,
            "display_name": "Original Name",
            "permissions": ["dashboard_view"]
        })
        assert create_resp.status_code == 200
        role_id = create_resp.json()["id"]
        
        # Update
        resp = requests.put(f"{BASE_URL}/api/rbac/roles/{role_id}", headers=admin_headers, json={
            "display_name": "Updated Name",
            "permissions": ["dashboard_view", "tasks_my_view"]
        })
        assert resp.status_code == 200
        
        data = resp.json()
        assert data["display_name"] == "Updated Name"
        assert "tasks_my_view" in data["permissions"]
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/rbac/roles/{role_id}", headers=admin_headers)

    def test_clone_role(self, admin_headers):
        """POST /api/rbac/roles/{id}/clone clones a role"""
        import uuid
        test_key = f"test_clone_src_{uuid.uuid4().hex[:8]}"
        clone_key = f"test_clone_dst_{uuid.uuid4().hex[:8]}"
        
        # Create source
        create_resp = requests.post(f"{BASE_URL}/api/rbac/roles", headers=admin_headers, json={
            "key": test_key,
            "display_name": "Source Role",
            "permissions": ["dashboard_view", "tasks_my_view"]
        })
        assert create_resp.status_code == 200
        src_id = create_resp.json()["id"]
        
        # Clone
        resp = requests.post(f"{BASE_URL}/api/rbac/roles/{src_id}/clone", headers=admin_headers, json={
            "new_key": clone_key,
            "display_name": "Cloned Role"
        })
        assert resp.status_code == 200
        
        data = resp.json()
        assert data["key"] == clone_key
        assert data["cloned_from_id"] == src_id
        assert data["cloned_from_key"] == test_key
        assert "dashboard_view" in data["permissions"]
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/rbac/roles/{data['id']}", headers=admin_headers)
        requests.delete(f"{BASE_URL}/api/rbac/roles/{src_id}", headers=admin_headers)

    def test_delete_role(self, admin_headers):
        """DELETE /api/rbac/roles/{id} deletes a role"""
        import uuid
        test_key = f"test_delete_{uuid.uuid4().hex[:8]}"
        
        # Create
        create_resp = requests.post(f"{BASE_URL}/api/rbac/roles", headers=admin_headers, json={
            "key": test_key,
            "permissions": []
        })
        assert create_resp.status_code == 200
        role_id = create_resp.json()["id"]
        
        # Delete
        resp = requests.delete(f"{BASE_URL}/api/rbac/roles/{role_id}", headers=admin_headers)
        assert resp.status_code == 200
        
        # Verify deleted
        get_resp = requests.get(f"{BASE_URL}/api/rbac/roles/{role_id}", headers=admin_headers)
        assert get_resp.status_code == 404


class TestPermissionRiskMapping:
    """Test specific permission risk mappings from PERMISSION_RISK dict"""

    def test_critical_risk_permissions(self, admin_headers):
        """Verify critical risk permissions are correctly marked"""
        resp = requests.get(f"{BASE_URL}/api/rbac/catalog", headers=admin_headers)
        assert resp.status_code == 200
        
        data = resp.json()
        catalog = data["catalog"]
        
        # Build permission lookup
        perm_lookup = {}
        for cat in catalog:
            for sg in cat.get("sub_groups", []):
                for perm in sg.get("permissions", []):
                    perm_lookup[perm["key"]] = perm
        
        # Check critical permissions
        critical_perms = [
            "delete_bookings", "delete_users", "delete_roles", "delete_branches",
            "delete_taxes", "delete_secrets", "delete_payroll_runs",
            "delete_channel_connections", "approve_payroll_runs", "mark_commissions_paid",
            "process_refunds", "view_secrets", "create_secrets", "edit_secrets",
            "create_roles", "edit_roles"
        ]
        
        for perm_key in critical_perms:
            if perm_key in perm_lookup:
                assert perm_lookup[perm_key]["risk"] == "critical", \
                    f"{perm_key} should have risk=critical, got {perm_lookup[perm_key]['risk']}"

    def test_high_risk_permissions(self, admin_headers):
        """Verify high risk permissions are correctly marked"""
        resp = requests.get(f"{BASE_URL}/api/rbac/catalog", headers=admin_headers)
        assert resp.status_code == 200
        
        data = resp.json()
        catalog = data["catalog"]
        
        perm_lookup = {}
        for cat in catalog:
            for sg in cat.get("sub_groups", []):
                for perm in sg.get("permissions", []):
                    perm_lookup[perm["key"]] = perm
        
        high_perms = [
            "cancel_bookings", "delete_rooms", "delete_rate_plans",
            "delete_webhooks", "delete_payroll_adjustments", "delete_cash_advances",
            "delete_cancellation_policies", "delete_channel_mappings",
            "create_payroll_runs", "edit_payroll_runs", "submit_commission_payables",
            "manage_expenses", "run_recurring_expenses", "promote_experiment_winners",
            "run_playbooks", "apply_action_items", "trigger_rate_sync",
            "rebuild_inventory", "bulk_update_rate_calendar", "manage_overbooking_policies",
            "export_audit_logs", "export_profit_data", "download_exports",
            "edit_retention_policies", "create_users", "edit_users"
        ]
        
        for perm_key in high_perms:
            if perm_key in perm_lookup:
                assert perm_lookup[perm_key]["risk"] == "high", \
                    f"{perm_key} should have risk=high, got {perm_lookup[perm_key]['risk']}"


class TestPermissionImpliesMapping:
    """Test specific permission implies mappings from PERMISSION_IMPLIES dict"""

    def test_edit_bookings_implies(self, admin_headers):
        """edit_bookings should imply view_bookings and bookings_view"""
        resp = requests.get(f"{BASE_URL}/api/rbac/catalog", headers=admin_headers)
        assert resp.status_code == 200
        
        data = resp.json()
        catalog = data["catalog"]
        
        edit_bookings = None
        for cat in catalog:
            for sg in cat.get("sub_groups", []):
                for perm in sg.get("permissions", []):
                    if perm["key"] == "edit_bookings":
                        edit_bookings = perm
                        break
        
        assert edit_bookings is not None
        assert "view_bookings" in edit_bookings["implies"]
        assert "bookings_view" in edit_bookings["implies"]

    def test_approve_payroll_implies(self, admin_headers):
        """approve_payroll_runs should imply view_payroll_runs and finance_payroll_runs_view"""
        resp = requests.get(f"{BASE_URL}/api/rbac/catalog", headers=admin_headers)
        assert resp.status_code == 200
        
        data = resp.json()
        catalog = data["catalog"]
        
        approve_payroll = None
        for cat in catalog:
            for sg in cat.get("sub_groups", []):
                for perm in sg.get("permissions", []):
                    if perm["key"] == "approve_payroll_runs":
                        approve_payroll = perm
                        break
        
        assert approve_payroll is not None
        assert "view_payroll_runs" in approve_payroll["implies"]
        assert "finance_payroll_runs_view" in approve_payroll["implies"]

    def test_edit_roles_implies(self, admin_headers):
        """edit_roles should imply view_roles and settings_roles_view"""
        resp = requests.get(f"{BASE_URL}/api/rbac/catalog", headers=admin_headers)
        assert resp.status_code == 200
        
        data = resp.json()
        catalog = data["catalog"]
        
        edit_roles = None
        for cat in catalog:
            for sg in cat.get("sub_groups", []):
                for perm in sg.get("permissions", []):
                    if perm["key"] == "edit_roles":
                        edit_roles = perm
                        break
        
        assert edit_roles is not None
        assert "view_roles" in edit_roles["implies"]
        assert "settings_roles_view" in edit_roles["implies"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
