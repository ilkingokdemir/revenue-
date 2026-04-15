"""
Iteration 83 - Notification Centre API Tests
Tests for:
1. GET /api/notifications - List notifications with unread_count
2. POST /api/notifications - Create notification
3. PUT /api/notifications/{id}/read - Mark single notification as read
4. PUT /api/notifications/read-all - Mark all notifications as read
5. POST /api/notifications/generate-check - Auto-generate alerts
6. DELETE /api/notifications/{id} - Delete notification
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestNotificationCentre:
    """Notification Centre API tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.token = login_response.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        
        yield
        
        # Cleanup - delete test notifications
        try:
            response = self.session.get(f"{BASE_URL}/api/notifications?limit=100")
            if response.status_code == 200:
                notifications = response.json().get("notifications", [])
                for n in notifications:
                    if n.get("title", "").startswith("TEST_"):
                        self.session.delete(f"{BASE_URL}/api/notifications/{n['id']}")
        except:
            pass
    
    # === GET /api/notifications ===
    
    def test_list_notifications_returns_structure(self):
        """GET /api/notifications returns notifications array and unread_count"""
        response = self.session.get(f"{BASE_URL}/api/notifications")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "notifications" in data, "Response should have 'notifications' key"
        assert "unread_count" in data, "Response should have 'unread_count' key"
        assert isinstance(data["notifications"], list), "notifications should be a list"
        assert isinstance(data["unread_count"], int), "unread_count should be an integer"
        print(f"✓ GET /api/notifications returns {len(data['notifications'])} notifications, {data['unread_count']} unread")
    
    def test_list_notifications_with_limit(self):
        """GET /api/notifications respects limit parameter"""
        response = self.session.get(f"{BASE_URL}/api/notifications?limit=5")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["notifications"]) <= 5, "Should respect limit parameter"
        print(f"✓ GET /api/notifications with limit=5 returns {len(data['notifications'])} notifications")
    
    def test_list_notifications_unread_only(self):
        """GET /api/notifications with unread_only=true filters unread"""
        response = self.session.get(f"{BASE_URL}/api/notifications?unread_only=true")
        assert response.status_code == 200
        
        data = response.json()
        for n in data["notifications"]:
            assert n.get("read") == False, "All notifications should be unread"
        print(f"✓ GET /api/notifications with unread_only=true returns only unread notifications")
    
    def test_list_notifications_requires_auth(self):
        """GET /api/notifications requires authentication"""
        no_auth_session = requests.Session()
        response = no_auth_session.get(f"{BASE_URL}/api/notifications")
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        print("✓ GET /api/notifications requires authentication")
    
    # === POST /api/notifications ===
    
    def test_create_notification(self):
        """POST /api/notifications creates a notification"""
        payload = {
            "type": "info",
            "title": "TEST_New Notification",
            "message": "This is a test notification message",
            "category": "general",
            "priority": "normal"
        }
        response = self.session.post(f"{BASE_URL}/api/notifications", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "id" in data, "Response should have 'id'"
        assert data["title"] == payload["title"], "Title should match"
        assert data["message"] == payload["message"], "Message should match"
        assert data["category"] == payload["category"], "Category should match"
        assert data["priority"] == payload["priority"], "Priority should match"
        assert data["read"] == False, "New notification should be unread"
        print(f"✓ POST /api/notifications created notification with id={data['id']}")
        
        # Verify it appears in list
        list_response = self.session.get(f"{BASE_URL}/api/notifications")
        notifications = list_response.json().get("notifications", [])
        found = any(n["id"] == data["id"] for n in notifications)
        assert found, "Created notification should appear in list"
        print("✓ Created notification appears in GET /api/notifications")
    
    def test_create_notification_with_all_fields(self):
        """POST /api/notifications with all optional fields"""
        payload = {
            "type": "warning",
            "title": "TEST_SLA Breach Alert",
            "message": "Maintenance request overdue",
            "category": "sla_breach",
            "target_user": "",
            "target_role": "manager",
            "link_to": "operations-hub",
            "priority": "high"
        }
        response = self.session.post(f"{BASE_URL}/api/notifications", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data["type"] == "warning"
        assert data["category"] == "sla_breach"
        assert data["priority"] == "high"
        assert data["target_role"] == "manager"
        assert data["link_to"] == "operations-hub"
        print(f"✓ POST /api/notifications with all fields created notification id={data['id']}")
    
    def test_create_notification_requires_admin_or_manager(self):
        """POST /api/notifications requires admin or manager role"""
        # This test verifies the endpoint is protected
        no_auth_session = requests.Session()
        response = no_auth_session.post(f"{BASE_URL}/api/notifications", json={
            "title": "TEST_Unauthorized",
            "message": "Should fail"
        })
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        print("✓ POST /api/notifications requires authentication")
    
    # === PUT /api/notifications/{id}/read ===
    
    def test_mark_notification_as_read(self):
        """PUT /api/notifications/{id}/read marks notification as read"""
        # First create a notification
        create_response = self.session.post(f"{BASE_URL}/api/notifications", json={
            "title": "TEST_Mark Read Test",
            "message": "Will be marked as read"
        })
        assert create_response.status_code == 200
        notif_id = create_response.json()["id"]
        
        # Mark as read
        read_response = self.session.put(f"{BASE_URL}/api/notifications/{notif_id}/read")
        assert read_response.status_code == 200, f"Expected 200, got {read_response.status_code}: {read_response.text}"
        
        data = read_response.json()
        assert data.get("status") == "read", "Response should confirm read status"
        print(f"✓ PUT /api/notifications/{notif_id}/read marked notification as read")
        
        # Verify it's marked as read in list
        list_response = self.session.get(f"{BASE_URL}/api/notifications")
        notifications = list_response.json().get("notifications", [])
        notif = next((n for n in notifications if n["id"] == notif_id), None)
        assert notif is not None, "Notification should exist"
        assert notif["read"] == True, "Notification should be marked as read"
        print("✓ Notification read status verified in GET /api/notifications")
    
    # === PUT /api/notifications/read-all ===
    
    def test_mark_all_notifications_as_read(self):
        """PUT /api/notifications/read-all marks all notifications as read"""
        # Create a few unread notifications
        for i in range(3):
            self.session.post(f"{BASE_URL}/api/notifications", json={
                "title": f"TEST_Bulk Read Test {i}",
                "message": f"Test notification {i}"
            })
        
        # Mark all as read
        response = self.session.put(f"{BASE_URL}/api/notifications/read-all")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "marked" in data, "Response should have 'marked' count"
        print(f"✓ PUT /api/notifications/read-all marked {data['marked']} notifications as read")
        
        # Verify unread count is 0
        list_response = self.session.get(f"{BASE_URL}/api/notifications")
        unread_count = list_response.json().get("unread_count", -1)
        assert unread_count == 0, f"Unread count should be 0, got {unread_count}"
        print("✓ Unread count is 0 after mark-all-read")
    
    # === POST /api/notifications/generate-check ===
    
    def test_generate_check_endpoint(self):
        """POST /api/notifications/generate-check auto-generates alerts"""
        response = self.session.post(f"{BASE_URL}/api/notifications/generate-check")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "generated" in data, "Response should have 'generated' count"
        assert isinstance(data["generated"], int), "generated should be an integer"
        print(f"✓ POST /api/notifications/generate-check generated {data['generated']} notifications")
    
    def test_generate_check_requires_admin_or_manager(self):
        """POST /api/notifications/generate-check requires admin or manager role"""
        no_auth_session = requests.Session()
        response = no_auth_session.post(f"{BASE_URL}/api/notifications/generate-check")
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        print("✓ POST /api/notifications/generate-check requires authentication")
    
    # === DELETE /api/notifications/{id} ===
    
    def test_delete_notification(self):
        """DELETE /api/notifications/{id} removes notification"""
        # First create a notification
        create_response = self.session.post(f"{BASE_URL}/api/notifications", json={
            "title": "TEST_Delete Test",
            "message": "Will be deleted"
        })
        assert create_response.status_code == 200
        notif_id = create_response.json()["id"]
        
        # Delete it
        delete_response = self.session.delete(f"{BASE_URL}/api/notifications/{notif_id}")
        assert delete_response.status_code == 200, f"Expected 200, got {delete_response.status_code}: {delete_response.text}"
        
        data = delete_response.json()
        assert data.get("status") == "deleted", "Response should confirm deletion"
        print(f"✓ DELETE /api/notifications/{notif_id} deleted notification")
        
        # Verify it's gone from list
        list_response = self.session.get(f"{BASE_URL}/api/notifications")
        notifications = list_response.json().get("notifications", [])
        found = any(n["id"] == notif_id for n in notifications)
        assert not found, "Deleted notification should not appear in list"
        print("✓ Deleted notification no longer appears in GET /api/notifications")
    
    def test_delete_notification_requires_admin_or_manager(self):
        """DELETE /api/notifications/{id} requires admin or manager role"""
        no_auth_session = requests.Session()
        response = no_auth_session.delete(f"{BASE_URL}/api/notifications/fake-id")
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        print("✓ DELETE /api/notifications requires authentication")
    
    # === Notification Categories ===
    
    def test_notification_categories(self):
        """Test different notification categories"""
        categories = ["sla_breach", "handover_alert", "compliance_due", "routine_alert", "general"]
        
        for category in categories:
            response = self.session.post(f"{BASE_URL}/api/notifications", json={
                "title": f"TEST_{category} notification",
                "message": f"Test for {category}",
                "category": category
            })
            assert response.status_code == 200, f"Failed to create {category} notification"
            assert response.json()["category"] == category
        
        print(f"✓ All notification categories work: {', '.join(categories)}")
    
    def test_notification_priorities(self):
        """Test different notification priorities"""
        priorities = ["normal", "high"]
        
        for priority in priorities:
            response = self.session.post(f"{BASE_URL}/api/notifications", json={
                "title": f"TEST_{priority} priority",
                "message": f"Test for {priority}",
                "priority": priority
            })
            assert response.status_code == 200, f"Failed to create {priority} priority notification"
            assert response.json()["priority"] == priority
        
        print(f"✓ All notification priorities work: {', '.join(priorities)}")
    
    def test_notification_types(self):
        """Test different notification types"""
        types = ["info", "warning", "error", "success"]
        
        for ntype in types:
            response = self.session.post(f"{BASE_URL}/api/notifications", json={
                "title": f"TEST_{ntype} type",
                "message": f"Test for {ntype}",
                "type": ntype
            })
            assert response.status_code == 200, f"Failed to create {ntype} type notification"
            assert response.json()["type"] == ntype
        
        print(f"✓ All notification types work: {', '.join(types)}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
