"""
Iteration 67 - Admin Panel Testing
Tests for:
- Role & Permission Management (CRUD for custom roles)
- User Permission Management
- Module Settings (per-module configuration)
- Auto Purchase Order Generation
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
PROPERTY_ID = "aldgate-flats"


class TestAdminPanelAuth:
    """Test authentication for admin panel access"""
    
    @pytest.fixture(scope="class")
    def session(self):
        """Create authenticated session"""
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        return s
    
    @pytest.fixture(scope="class")
    def auth_token(self, session):
        """Get authentication token"""
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in response"
        return data["token"]
    
    @pytest.fixture(scope="class")
    def auth_session(self, session, auth_token):
        """Session with auth header"""
        session.headers.update({"Authorization": f"Bearer {auth_token}"})
        return session
    
    def test_login_success(self, session):
        """Test admin login works"""
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        # Role may be at top level or nested in user object
        role = data.get("role") or data.get("user", {}).get("role")
        assert role == "admin", f"Expected admin role, got: {role}"
        print(f"✓ Admin login successful, role: {role}")


class TestRolesManagement:
    """Test Role & Permission Management APIs"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        """Create authenticated session"""
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        response = s.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        token = response.json()["token"]
        s.headers.update({"Authorization": f"Bearer {token}"})
        return s
    
    def test_list_roles(self, auth_session):
        """GET /api/admin/roles - Lists built-in + custom roles"""
        response = auth_session.get(f"{BASE_URL}/api/admin/roles")
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert "roles" in data
        assert "modules" in data
        assert "actions" in data
        
        # Verify built-in roles exist
        role_ids = [r["id"] for r in data["roles"]]
        assert "admin" in role_ids, "Admin role missing"
        assert "manager" in role_ids, "Manager role missing"
        assert "receptionist" in role_ids, "Receptionist role missing"
        
        # Verify modules (14 modules)
        assert len(data["modules"]) == 14, f"Expected 14 modules, got {len(data['modules'])}"
        
        # Verify actions (6 actions)
        assert len(data["actions"]) == 6, f"Expected 6 actions, got {len(data['actions'])}"
        expected_actions = ["view", "create", "edit", "delete", "export", "manage_settings"]
        for action in expected_actions:
            assert action in data["actions"], f"Action {action} missing"
        
        # Verify built-in roles have is_builtin=True
        for role in data["roles"]:
            if role["id"] in ["admin", "manager", "receptionist"]:
                assert role["is_builtin"] == True, f"Built-in role {role['id']} should have is_builtin=True"
        
        print(f"✓ List roles: {len(data['roles'])} roles, {len(data['modules'])} modules, {len(data['actions'])} actions")
    
    def test_create_custom_role(self, auth_session):
        """POST /api/admin/roles - Creates custom role with specific permissions"""
        unique_id = str(uuid.uuid4())[:6]
        role_data = {
            "id": f"test_role_{unique_id}",
            "name": f"Test Role {unique_id}",
            "description": "Test role for iteration 67",
            "permissions": {
                "dashboard": ["view"],
                "reviews": ["view", "create"],
                "bookings": ["view", "create", "edit"],
                "pos": ["view", "create", "edit", "delete"]
            }
        }
        
        response = auth_session.post(f"{BASE_URL}/api/admin/roles", json=role_data)
        assert response.status_code == 200, f"Create role failed: {response.text}"
        data = response.json()
        
        # Verify created role
        assert data["id"] == role_data["id"]
        assert data["name"] == role_data["name"]
        assert data["is_builtin"] == False
        assert "permissions" in data
        assert data["permissions"]["dashboard"] == ["view"]
        assert "create" in data["permissions"]["reviews"]
        
        print(f"✓ Created custom role: {data['id']}")
        return data["id"]
    
    def test_update_custom_role_permissions(self, auth_session):
        """PUT /api/admin/roles/{id} - Updates custom role permissions"""
        # First create a role to update
        unique_id = str(uuid.uuid4())[:6]
        create_response = auth_session.post(f"{BASE_URL}/api/admin/roles", json={
            "id": f"update_test_{unique_id}",
            "name": f"Update Test {unique_id}",
            "permissions": {"dashboard": ["view"]}
        })
        assert create_response.status_code == 200
        role_id = create_response.json()["id"]
        
        # Update permissions
        update_data = {
            "permissions": {
                "dashboard": ["view", "export"],
                "reviews": ["view", "create", "edit"],
                "stock": ["view", "create", "edit", "delete", "export"]
            }
        }
        
        response = auth_session.put(f"{BASE_URL}/api/admin/roles/{role_id}", json=update_data)
        assert response.status_code == 200, f"Update role failed: {response.text}"
        data = response.json()
        
        # Verify updated permissions
        assert "export" in data["permissions"]["dashboard"]
        assert "edit" in data["permissions"]["reviews"]
        assert len(data["permissions"]["stock"]) == 5
        
        print(f"✓ Updated role permissions: {role_id}")
        
        # Cleanup
        auth_session.delete(f"{BASE_URL}/api/admin/roles/{role_id}")
    
    def test_cannot_modify_builtin_roles(self, auth_session):
        """PUT /api/admin/roles/{id} - Cannot modify built-in roles"""
        response = auth_session.put(f"{BASE_URL}/api/admin/roles/admin", json={
            "permissions": {"dashboard": []}
        })
        assert response.status_code == 400, "Should not be able to modify built-in role"
        print("✓ Cannot modify built-in roles (admin)")
        
        response = auth_session.put(f"{BASE_URL}/api/admin/roles/manager", json={
            "permissions": {"dashboard": []}
        })
        assert response.status_code == 400
        print("✓ Cannot modify built-in roles (manager)")
    
    def test_delete_custom_role(self, auth_session):
        """DELETE /api/admin/roles/{id} - Deletes custom role"""
        # Create a role to delete
        unique_id = str(uuid.uuid4())[:6]
        create_response = auth_session.post(f"{BASE_URL}/api/admin/roles", json={
            "id": f"delete_test_{unique_id}",
            "name": f"Delete Test {unique_id}",
            "permissions": {}
        })
        assert create_response.status_code == 200
        role_id = create_response.json()["id"]
        
        # Delete the role
        response = auth_session.delete(f"{BASE_URL}/api/admin/roles/{role_id}")
        assert response.status_code == 200, f"Delete role failed: {response.text}"
        assert response.json()["status"] == "deleted"
        
        # Verify role is deleted
        list_response = auth_session.get(f"{BASE_URL}/api/admin/roles")
        role_ids = [r["id"] for r in list_response.json()["roles"]]
        assert role_id not in role_ids, "Role should be deleted"
        
        print(f"✓ Deleted custom role: {role_id}")
    
    def test_cannot_delete_builtin_roles(self, auth_session):
        """DELETE /api/admin/roles/{id} - Cannot delete built-in roles"""
        for role_id in ["admin", "manager", "receptionist"]:
            response = auth_session.delete(f"{BASE_URL}/api/admin/roles/{role_id}")
            assert response.status_code == 400, f"Should not be able to delete built-in role {role_id}"
        print("✓ Cannot delete built-in roles")


class TestUserPermissions:
    """Test User Permission Management APIs"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        """Create authenticated session"""
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        response = s.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        token = response.json()["token"]
        s.headers.update({"Authorization": f"Bearer {token}"})
        return s
    
    def test_list_users_with_permissions(self, auth_session):
        """GET /api/admin/users - Lists users with effective_permissions field"""
        response = auth_session.get(f"{BASE_URL}/api/admin/users")
        assert response.status_code == 200
        users = response.json()
        
        assert isinstance(users, list)
        assert len(users) > 0, "Should have at least one user"
        
        # Verify user structure
        for user in users:
            assert "email" in user
            assert "role" in user
            assert "effective_permissions" in user, f"User {user['email']} missing effective_permissions"
            assert "password" not in user, "Password should not be exposed"
        
        # Find admin user and verify permissions
        admin_user = next((u for u in users if u["email"] == ADMIN_EMAIL), None)
        assert admin_user is not None, "Admin user not found"
        assert admin_user["role"] == "admin"
        assert "dashboard" in admin_user["effective_permissions"]
        
        print(f"✓ List users: {len(users)} users with effective_permissions")
    
    def test_update_user_role(self, auth_session):
        """PUT /api/admin/users/{id}/permissions - Updates user role"""
        # Get list of users
        users_response = auth_session.get(f"{BASE_URL}/api/admin/users")
        users = users_response.json()
        
        # Find a non-admin user to update (or skip if only admin exists)
        non_admin_user = next((u for u in users if u["role"] != "admin"), None)
        
        if non_admin_user:
            original_role = non_admin_user["role"]
            user_id = non_admin_user["id"]
            
            # Update to manager role
            response = auth_session.put(f"{BASE_URL}/api/admin/users/{user_id}/permissions", json={
                "role": "manager"
            })
            assert response.status_code == 200, f"Update user role failed: {response.text}"
            data = response.json()
            assert data["role"] == "manager"
            
            # Restore original role
            auth_session.put(f"{BASE_URL}/api/admin/users/{user_id}/permissions", json={
                "role": original_role
            })
            
            print(f"✓ Updated user role: {user_id} to manager and back to {original_role}")
        else:
            print("✓ Skipped user role update (only admin user exists)")


class TestModuleSettings:
    """Test Module Settings APIs"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        """Create authenticated session"""
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        response = s.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        token = response.json()["token"]
        s.headers.update({"Authorization": f"Bearer {token}"})
        return s
    
    def test_get_pos_module_settings(self, auth_session):
        """GET /api/admin/module-settings/pos/{property_id} - Returns POS settings"""
        response = auth_session.get(f"{BASE_URL}/api/admin/module-settings/pos/{PROPERTY_ID}")
        assert response.status_code == 200, f"Get POS settings failed: {response.text}"
        data = response.json()
        
        # Verify POS settings structure (10 settings)
        assert data["module"] == "pos"
        assert data["property_id"] == PROPERTY_ID
        assert "tax_rate" in data
        assert "service_charge_pct" in data
        assert "allow_discounts" in data
        assert "max_discount_pct" in data
        assert "kitchen_display_enabled" in data
        assert "auto_print_receipt" in data
        assert "require_table_number" in data
        assert "receipt_header" in data
        assert "receipt_footer" in data
        assert "order_numbering_prefix" in data
        
        print(f"✓ Get POS settings: tax_rate={data['tax_rate']}, allow_discounts={data['allow_discounts']}")
    
    def test_get_bookings_module_settings(self, auth_session):
        """GET /api/admin/module-settings/bookings/{property_id} - Returns Bookings settings"""
        response = auth_session.get(f"{BASE_URL}/api/admin/module-settings/bookings/{PROPERTY_ID}")
        assert response.status_code == 200
        data = response.json()
        
        # Verify Bookings settings structure (9 settings)
        assert data["module"] == "bookings"
        assert "check_in_time" in data
        assert "check_out_time" in data
        assert "cancellation_hours" in data
        assert "deposit_pct" in data
        assert "overbooking_buffer" in data
        assert "min_stay" in data
        assert "auto_confirm" in data
        assert "send_confirmation_email" in data
        assert "pre_arrival_hours" in data
        
        print(f"✓ Get Bookings settings: check_in={data['check_in_time']}, check_out={data['check_out_time']}")
    
    def test_get_accounting_module_settings(self, auth_session):
        """GET /api/admin/module-settings/accounting/{property_id} - Returns Accounting settings"""
        response = auth_session.get(f"{BASE_URL}/api/admin/module-settings/accounting/{PROPERTY_ID}")
        assert response.status_code == 200
        data = response.json()
        
        assert data["module"] == "accounting"
        assert "financial_year_start" in data
        assert "default_currency" in data
        assert "tax_rate" in data
        assert "auto_post_pos" in data
        assert "auto_post_bookings" in data
        assert "invoice_prefix" in data
        assert "invoice_due_days" in data
        
        print(f"✓ Get Accounting settings: currency={data['default_currency']}, tax_rate={data['tax_rate']}")
    
    def test_get_messaging_module_settings(self, auth_session):
        """GET /api/admin/module-settings/messaging/{property_id} - Returns Messaging settings"""
        response = auth_session.get(f"{BASE_URL}/api/admin/module-settings/messaging/{PROPERTY_ID}")
        assert response.status_code == 200
        data = response.json()
        
        assert data["module"] == "messaging"
        assert "auto_reply_enabled" in data
        assert "auto_reply_message" in data
        assert "business_hours_start" in data
        assert "business_hours_end" in data
        assert "response_time_target_minutes" in data
        assert "auto_translate" in data
        
        print(f"✓ Get Messaging settings: auto_reply={data['auto_reply_enabled']}")
    
    def test_get_reviews_module_settings(self, auth_session):
        """GET /api/admin/module-settings/reviews/{property_id} - Returns Reviews settings"""
        response = auth_session.get(f"{BASE_URL}/api/admin/module-settings/reviews/{PROPERTY_ID}")
        assert response.status_code == 200
        data = response.json()
        
        assert data["module"] == "reviews"
        assert "auto_respond" in data
        assert "review_request_delay_hours" in data
        assert "minimum_rating_alert" in data
        assert "request_review_on_checkout" in data
        
        print(f"✓ Get Reviews settings: auto_respond={data['auto_respond']}")
    
    def test_get_stock_module_settings(self, auth_session):
        """GET /api/admin/module-settings/stock/{property_id} - Returns Stock settings"""
        response = auth_session.get(f"{BASE_URL}/api/admin/module-settings/stock/{PROPERTY_ID}")
        assert response.status_code == 200
        data = response.json()
        
        assert data["module"] == "stock"
        assert "low_stock_alert_enabled" in data
        assert "auto_reorder_enabled" in data
        assert "wastage_tracking" in data
        assert "default_par_level" in data
        assert "default_reorder_level" in data
        assert "stock_count_frequency" in data
        
        print(f"✓ Get Stock settings: low_stock_alert={data['low_stock_alert_enabled']}")
    
    def test_get_surveys_module_settings(self, auth_session):
        """GET /api/admin/module-settings/surveys/{property_id} - Returns Surveys settings"""
        response = auth_session.get(f"{BASE_URL}/api/admin/module-settings/surveys/{PROPERTY_ID}")
        assert response.status_code == 200
        data = response.json()
        
        assert data["module"] == "surveys"
        assert "auto_send_on_checkout" in data
        assert "send_delay_hours" in data
        assert "reminder_enabled" in data
        assert "anonymous_allowed" in data
        
        print(f"✓ Get Surveys settings: auto_send={data['auto_send_on_checkout']}")
    
    def test_update_module_settings(self, auth_session):
        """PUT /api/admin/module-settings/{module}/{property_id} - Saves module settings"""
        # Get current POS settings
        get_response = auth_session.get(f"{BASE_URL}/api/admin/module-settings/pos/{PROPERTY_ID}")
        original_settings = get_response.json()
        original_tax_rate = original_settings.get("tax_rate", 20)
        
        # Update tax rate
        new_tax_rate = 25 if original_tax_rate != 25 else 20
        update_response = auth_session.put(f"{BASE_URL}/api/admin/module-settings/pos/{PROPERTY_ID}", json={
            "tax_rate": new_tax_rate
        })
        assert update_response.status_code == 200, f"Update settings failed: {update_response.text}"
        data = update_response.json()
        assert data["tax_rate"] == new_tax_rate
        assert "updated_at" in data
        assert "updated_by" in data
        
        # Verify persistence with GET
        verify_response = auth_session.get(f"{BASE_URL}/api/admin/module-settings/pos/{PROPERTY_ID}")
        assert verify_response.json()["tax_rate"] == new_tax_rate
        
        # Restore original
        auth_session.put(f"{BASE_URL}/api/admin/module-settings/pos/{PROPERTY_ID}", json={
            "tax_rate": original_tax_rate
        })
        
        print(f"✓ Updated POS settings: tax_rate {original_tax_rate} -> {new_tax_rate} -> {original_tax_rate}")
    
    def test_get_all_module_settings(self, auth_session):
        """GET /api/admin/module-settings-all/{property_id} - Returns all module settings"""
        response = auth_session.get(f"{BASE_URL}/api/admin/module-settings-all/{PROPERTY_ID}")
        assert response.status_code == 200
        data = response.json()
        
        # Verify all modules are present
        expected_modules = ["pos", "bookings", "accounting", "messaging", "reviews", "stock", "surveys"]
        for module in expected_modules:
            assert module in data, f"Module {module} missing from all settings"
            assert data[module]["module"] == module
        
        print(f"✓ Get all module settings: {len(data)} modules")


class TestPurchaseOrders:
    """Test Auto Purchase Order APIs"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        """Create authenticated session"""
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        response = s.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        token = response.json()["token"]
        s.headers.update({"Authorization": f"Bearer {token}"})
        return s
    
    def test_list_purchase_orders(self, auth_session):
        """GET /api/admin/purchase-orders/{property_id} - Lists purchase orders"""
        response = auth_session.get(f"{BASE_URL}/api/admin/purchase-orders/{PROPERTY_ID}")
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        
        # If there are POs, verify structure
        if len(data) > 0:
            po = data[0]
            assert "id" in po
            assert "po_number" in po
            assert "property_id" in po
            assert "supplier" in po
            assert "status" in po
            assert "items" in po
            assert "total_items" in po
            assert "total_cost" in po
            assert "created_at" in po
        
        print(f"✓ List purchase orders: {len(data)} POs")
    
    def test_generate_auto_purchase_orders(self, auth_session):
        """POST /api/admin/auto-purchase-orders/{property_id} - Generates POs for low stock items"""
        response = auth_session.post(f"{BASE_URL}/api/admin/auto-purchase-orders/{PROPERTY_ID}")
        assert response.status_code == 200, f"Generate POs failed: {response.text}"
        data = response.json()
        
        assert "status" in data
        assert "message" in data
        assert "orders" in data
        
        if data["status"] == "generated":
            assert len(data["orders"]) > 0
            po = data["orders"][0]
            assert "id" in po
            assert "po_number" in po
            assert "supplier" in po
            assert "status" in po
            assert po["status"] == "draft"
            assert "items" in po
            assert "total_cost" in po
            print(f"✓ Generated {len(data['orders'])} purchase orders")
        else:
            assert data["status"] == "no_orders_needed"
            print(f"✓ No POs needed: {data['message']}")
    
    def test_update_po_status_approve(self, auth_session):
        """PUT /api/admin/purchase-orders/{po_id}/status - Updates PO status to approved"""
        # First generate a PO or get existing draft
        list_response = auth_session.get(f"{BASE_URL}/api/admin/purchase-orders/{PROPERTY_ID}")
        pos = list_response.json()
        
        draft_po = next((po for po in pos if po["status"] == "draft"), None)
        
        if draft_po:
            po_id = draft_po["id"]
            
            # Approve the PO
            response = auth_session.put(f"{BASE_URL}/api/admin/purchase-orders/{po_id}/status", json={
                "status": "approved"
            })
            assert response.status_code == 200, f"Approve PO failed: {response.text}"
            data = response.json()
            assert data["status"] == "approved"
            assert "updated_at" in data
            
            print(f"✓ Approved PO: {draft_po['po_number']}")
        else:
            print("✓ Skipped PO approval (no draft POs)")
    
    def test_update_po_status_received_restocks(self, auth_session):
        """PUT /api/admin/purchase-orders/{po_id}/status - Marks PO as received and restocks"""
        # Get approved POs
        list_response = auth_session.get(f"{BASE_URL}/api/admin/purchase-orders/{PROPERTY_ID}")
        pos = list_response.json()
        
        approved_po = next((po for po in pos if po["status"] == "approved"), None)
        
        if approved_po:
            po_id = approved_po["id"]
            
            # Mark as received
            response = auth_session.put(f"{BASE_URL}/api/admin/purchase-orders/{po_id}/status", json={
                "status": "received"
            })
            assert response.status_code == 200, f"Receive PO failed: {response.text}"
            data = response.json()
            assert data["status"] == "received"
            assert "received_at" in data
            
            print(f"✓ Received PO: {approved_po['po_number']} - stock should be updated")
        else:
            print("✓ Skipped PO receive (no approved POs)")
    
    def test_invalid_po_status(self, auth_session):
        """PUT /api/admin/purchase-orders/{po_id}/status - Invalid status returns 400"""
        # Get any PO
        list_response = auth_session.get(f"{BASE_URL}/api/admin/purchase-orders/{PROPERTY_ID}")
        pos = list_response.json()
        
        if len(pos) > 0:
            po_id = pos[0]["id"]
            
            response = auth_session.put(f"{BASE_URL}/api/admin/purchase-orders/{po_id}/status", json={
                "status": "invalid_status"
            })
            assert response.status_code == 400, "Invalid status should return 400"
            print("✓ Invalid PO status returns 400")
        else:
            print("✓ Skipped invalid status test (no POs)")


class TestAdminPanelAccessControl:
    """Test access control for admin panel"""
    
    def test_unauthenticated_access_denied(self):
        """Admin endpoints require authentication"""
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        
        # Try to access admin endpoints without auth
        endpoints = [
            f"{BASE_URL}/api/admin/roles",
            f"{BASE_URL}/api/admin/users",
            f"{BASE_URL}/api/admin/module-settings/pos/{PROPERTY_ID}",
            f"{BASE_URL}/api/admin/purchase-orders/{PROPERTY_ID}"
        ]
        
        for endpoint in endpoints:
            response = s.get(endpoint)
            assert response.status_code in [401, 403], f"Endpoint {endpoint} should require auth"
        
        print("✓ All admin endpoints require authentication")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
