"""
Iteration 76 - Maintenance Module Tests
Tests for the comprehensive maintenance upgrade with 8 features:
1. Photo/Video Attachments
2. Auto-Assignment & Notifications
3. SLA Tracking & Response Times
4. Cost Tracking
5. Kanban Board View (frontend)
6. Priority Levels (Critical/High/Medium/Low)
7. Comments/Activity Log
8. Recurring/Preventive Maintenance
"""
import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://review-hub-108.preview.emergentagent.com').rstrip('/')
TEST_PROPERTY = "aldgate-flats"

class TestMaintenanceModule:
    """Test suite for Maintenance Module endpoints"""
    
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
        self.token = login_response.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        yield
        # Cleanup handled in individual tests
    
    # ==================== ISSUES CRUD ====================
    
    def test_01_create_issue_with_auto_assignment_and_sla(self):
        """Test POST /api/maintenance/issues - creates issue with auto-department assignment and SLA deadline"""
        payload = {
            "property_id": TEST_PROPERTY,
            "title": f"TEST_Leaking faucet in Room 101_{uuid.uuid4().hex[:6]}",
            "description": "Water is dripping from the bathroom faucet",
            "category": "plumbing",
            "priority": "high",
            "location": "Room 101",
            "room_number": "101"
        }
        response = self.session.post(f"{BASE_URL}/api/maintenance/issues", json=payload)
        assert response.status_code == 200, f"Create issue failed: {response.text}"
        
        data = response.json()
        # Verify auto-assignment
        assert data["assigned_department"] == "maintenance", "Plumbing should auto-assign to maintenance dept"
        # Verify SLA calculation (high priority = 8 hours)
        assert data["sla_hours"] == 8, "High priority should have 8h SLA"
        assert data["sla_deadline"], "SLA deadline should be set"
        assert data["status"] == "open", "New issue should be open"
        assert data["sla_breached"] == False, "New issue should not be breached"
        assert "id" in data, "Issue should have an ID"
        
        # Store for later tests
        self.__class__.test_issue_id = data["id"]
        print(f"Created issue: {data['id']}")
    
    def test_02_create_critical_issue_sla_2h(self):
        """Test critical priority has 2h SLA"""
        payload = {
            "property_id": TEST_PROPERTY,
            "title": f"TEST_Fire alarm malfunction_{uuid.uuid4().hex[:6]}",
            "description": "Fire alarm not working in lobby",
            "category": "safety",
            "priority": "critical",
            "location": "Lobby"
        }
        response = self.session.post(f"{BASE_URL}/api/maintenance/issues", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data["sla_hours"] == 2, "Critical priority should have 2h SLA"
        assert data["assigned_department"] == "management", "Safety issues should go to management"
        self.__class__.critical_issue_id = data["id"]
    
    def test_03_create_low_priority_issue_sla_72h(self):
        """Test low priority has 72h SLA"""
        payload = {
            "property_id": TEST_PROPERTY,
            "title": f"TEST_Paint touch-up needed_{uuid.uuid4().hex[:6]}",
            "description": "Minor paint chip on wall",
            "category": "general",
            "priority": "low",
            "location": "Hallway"
        }
        response = self.session.post(f"{BASE_URL}/api/maintenance/issues", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data["sla_hours"] == 72, "Low priority should have 72h SLA"
        self.__class__.low_issue_id = data["id"]
    
    def test_04_list_issues_with_filters(self):
        """Test GET /api/maintenance/issues/{property_id} - lists issues with filters"""
        # List all issues for property
        response = self.session.get(f"{BASE_URL}/api/maintenance/issues/{TEST_PROPERTY}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list), "Should return a list"
        
        # Filter by status
        response = self.session.get(f"{BASE_URL}/api/maintenance/issues/{TEST_PROPERTY}?status=open")
        assert response.status_code == 200
        open_issues = response.json()
        for issue in open_issues:
            assert issue["status"] == "open", "Filter should only return open issues"
        
        # Filter by priority
        response = self.session.get(f"{BASE_URL}/api/maintenance/issues/{TEST_PROPERTY}?priority=critical")
        assert response.status_code == 200
        critical_issues = response.json()
        for issue in critical_issues:
            assert issue["priority"] == "critical", "Filter should only return critical issues"
        
        # Filter by category
        response = self.session.get(f"{BASE_URL}/api/maintenance/issues/{TEST_PROPERTY}?category=plumbing")
        assert response.status_code == 200
        plumbing_issues = response.json()
        for issue in plumbing_issues:
            assert issue["category"] == "plumbing", "Filter should only return plumbing issues"
        
        print(f"Found {len(data)} total issues for {TEST_PROPERTY}")
    
    def test_05_list_all_properties_issues(self):
        """Test GET /api/maintenance/issues/all - returns issues across all properties"""
        response = self.session.get(f"{BASE_URL}/api/maintenance/issues/all")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list), "Should return a list"
        print(f"Found {len(data)} issues across all properties")
    
    def test_06_get_issue_detail(self):
        """Test GET /api/maintenance/issues/detail/{issue_id}"""
        issue_id = getattr(self.__class__, 'test_issue_id', None)
        if not issue_id:
            pytest.skip("No test issue created")
        
        response = self.session.get(f"{BASE_URL}/api/maintenance/issues/detail/{issue_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == issue_id
        assert "title" in data
        assert "sla_deadline" in data
        assert "comments" in data
        assert "photos" in data
    
    def test_07_update_issue_status_transitions(self):
        """Test PUT /api/maintenance/issues/{issue_id} - tracks status transitions"""
        issue_id = getattr(self.__class__, 'test_issue_id', None)
        if not issue_id:
            pytest.skip("No test issue created")
        
        # Acknowledge the issue
        response = self.session.put(f"{BASE_URL}/api/maintenance/issues/{issue_id}", json={
            "status": "acknowledged"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "acknowledged"
        assert data["acknowledged_at"], "acknowledged_at should be set"
        
        # Start work on the issue
        response = self.session.put(f"{BASE_URL}/api/maintenance/issues/{issue_id}", json={
            "status": "in_progress"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "in_progress"
        assert data["started_at"], "started_at should be set"
        
        # Resolve the issue
        response = self.session.put(f"{BASE_URL}/api/maintenance/issues/{issue_id}", json={
            "status": "resolved",
            "resolution_notes": "Fixed the leaking faucet by replacing washer"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "resolved"
        assert data["resolved_at"], "resolved_at should be set"
        print(f"Issue {issue_id} status transitions verified")
    
    # ==================== COMMENTS ====================
    
    def test_08_add_comment_to_issue(self):
        """Test POST /api/maintenance/issues/{issue_id}/comment - adds comment to issue"""
        issue_id = getattr(self.__class__, 'critical_issue_id', None)
        if not issue_id:
            pytest.skip("No critical issue created")
        
        response = self.session.post(f"{BASE_URL}/api/maintenance/issues/{issue_id}/comment", json={
            "text": "Technician dispatched to check the fire alarm"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["text"] == "Technician dispatched to check the fire alarm"
        assert "author" in data
        assert "created_at" in data
        assert "id" in data
        
        # Add another comment
        response = self.session.post(f"{BASE_URL}/api/maintenance/issues/{issue_id}/comment", json={
            "text": "Fire alarm battery replaced, system tested and working"
        })
        assert response.status_code == 200
        
        # Verify comments are stored
        response = self.session.get(f"{BASE_URL}/api/maintenance/issues/detail/{issue_id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["comments"]) >= 2, "Should have at least 2 comments"
        print(f"Added comments to issue {issue_id}")
    
    def test_09_comment_on_nonexistent_issue(self):
        """Test adding comment to non-existent issue returns 404"""
        response = self.session.post(f"{BASE_URL}/api/maintenance/issues/nonexistent-id/comment", json={
            "text": "This should fail"
        })
        assert response.status_code == 404
    
    # ==================== COST TRACKING ====================
    
    def test_10_update_cost_tracking(self):
        """Test PUT /api/maintenance/issues/{issue_id}/cost - updates cost tracking"""
        issue_id = getattr(self.__class__, 'test_issue_id', None)
        if not issue_id:
            pytest.skip("No test issue created")
        
        response = self.session.put(f"{BASE_URL}/api/maintenance/issues/{issue_id}/cost", json={
            "estimated_cost": 50,
            "actual_cost": 35,
            "cost_notes": "Washer replacement - parts £15, labour £20",
            "materials": [
                {"name": "Faucet washer", "cost": 5},
                {"name": "Plumber tape", "cost": 10}
            ]
        })
        assert response.status_code == 200
        
        # Verify cost is saved
        response = self.session.get(f"{BASE_URL}/api/maintenance/issues/detail/{issue_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["estimated_cost"] == 50
        assert data["actual_cost"] == 35
        assert data["cost_notes"] == "Washer replacement - parts £15, labour £20"
        assert len(data["materials"]) == 2
        print(f"Cost tracking updated for issue {issue_id}")
    
    # ==================== STATS & ANALYTICS ====================
    
    def test_11_get_stats_with_breakdowns(self):
        """Test GET /api/maintenance/stats/{property_id} - returns stats with category/priority breakdown"""
        response = self.session.get(f"{BASE_URL}/api/maintenance/stats/{TEST_PROPERTY}")
        assert response.status_code == 200
        data = response.json()
        
        # Verify stats structure
        assert "total" in data
        assert "open" in data
        assert "in_progress" in data
        assert "resolved" in data
        assert "overdue" in data
        assert "by_category" in data
        assert "by_priority" in data
        assert "costs" in data
        
        # Verify costs structure
        assert "total_estimated" in data["costs"]
        assert "total_actual" in data["costs"]
        
        print(f"Stats for {TEST_PROPERTY}: total={data['total']}, open={data['open']}, resolved={data['resolved']}")
    
    def test_12_get_stats_all_properties(self):
        """Test GET /api/maintenance/stats/all - returns stats across all properties"""
        response = self.session.get(f"{BASE_URL}/api/maintenance/stats/all")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "costs" in data
        print(f"All properties stats: total={data['total']}")
    
    # ==================== SLA CHECK ====================
    
    def test_13_check_sla_breaches(self):
        """Test POST /api/maintenance/check-sla/{property_id} - checks and marks SLA breaches"""
        response = self.session.post(f"{BASE_URL}/api/maintenance/check-sla/{TEST_PROPERTY}")
        assert response.status_code == 200
        data = response.json()
        assert "checked" in data
        assert "newly_breached" in data
        print(f"SLA check: checked={data['checked']}, newly_breached={data['newly_breached']}")
    
    # ==================== RECURRING MAINTENANCE ====================
    
    def test_14_create_recurring_schedule(self):
        """Test POST /api/maintenance/recurring - create recurring maintenance schedule"""
        payload = {
            "property_id": TEST_PROPERTY,
            "title": f"TEST_Monthly HVAC filter check_{uuid.uuid4().hex[:6]}",
            "description": "Check and replace HVAC filters in all rooms",
            "category": "hvac",
            "priority": "medium",
            "frequency": "monthly",
            "location": "All rooms",
            "assigned_to": "Maintenance Team"
        }
        response = self.session.post(f"{BASE_URL}/api/maintenance/recurring", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data["frequency"] == "monthly"
        assert data["is_active"] == True
        assert "next_due" in data
        assert "id" in data
        
        self.__class__.recurring_id = data["id"]
        print(f"Created recurring schedule: {data['id']}")
    
    def test_15_create_weekly_recurring(self):
        """Test weekly recurring schedule"""
        payload = {
            "property_id": TEST_PROPERTY,
            "title": f"TEST_Weekly pool maintenance_{uuid.uuid4().hex[:6]}",
            "description": "Check pool chemicals and clean filters",
            "category": "general",
            "priority": "medium",
            "frequency": "weekly",
            "location": "Pool area"
        }
        response = self.session.post(f"{BASE_URL}/api/maintenance/recurring", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["frequency"] == "weekly"
        self.__class__.weekly_recurring_id = data["id"]
    
    def test_16_list_recurring_schedules(self):
        """Test GET /api/maintenance/recurring/{property_id} - list recurring schedules"""
        response = self.session.get(f"{BASE_URL}/api/maintenance/recurring/{TEST_PROPERTY}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Found {len(data)} recurring schedules for {TEST_PROPERTY}")
    
    def test_17_update_recurring_schedule(self):
        """Test PUT /api/maintenance/recurring/{schedule_id} - update recurring schedule"""
        schedule_id = getattr(self.__class__, 'recurring_id', None)
        if not schedule_id:
            pytest.skip("No recurring schedule created")
        
        response = self.session.put(f"{BASE_URL}/api/maintenance/recurring/{schedule_id}", json={
            "priority": "high",
            "is_active": True
        })
        assert response.status_code == 200
        data = response.json()
        assert data["priority"] == "high"
    
    def test_18_generate_recurring_tasks(self):
        """Test POST /api/maintenance/recurring/generate/{property_id} - generates issues from due schedules"""
        response = self.session.post(f"{BASE_URL}/api/maintenance/recurring/generate/{TEST_PROPERTY}")
        assert response.status_code == 200
        data = response.json()
        assert "generated" in data
        assert "schedules_checked" in data
        print(f"Generated {data['generated']} tasks from {data['schedules_checked']} schedules")
    
    # ==================== PHOTO UPLOAD ====================
    
    def test_19_upload_photo_to_issue(self):
        """Test POST /api/maintenance/upload-photo/{issue_id} - uploads photo for issue"""
        issue_id = getattr(self.__class__, 'critical_issue_id', None)
        if not issue_id:
            pytest.skip("No critical issue created")
        
        # Create a simple test image (1x1 pixel PNG)
        import base64
        # Minimal valid PNG
        png_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )
        
        files = {"file": ("test_photo.png", png_data, "image/png")}
        
        # Use session with cookies for file upload (remove Content-Type header)
        upload_session = requests.Session()
        upload_session.cookies = self.session.cookies
        upload_session.headers.update({"Authorization": f"Bearer {self.token}"})
        
        response = upload_session.post(
            f"{BASE_URL}/api/maintenance/upload-photo/{issue_id}",
            files=files
        )
        assert response.status_code == 200, f"Photo upload failed: {response.text}"
        data = response.json()
        assert data["status"] == "uploaded"
        assert "url" in data
        assert data["url"].startswith("/api/uploads/maintenance/")
        
        # Verify photo is attached to issue
        response = self.session.get(f"{BASE_URL}/api/maintenance/issues/detail/{issue_id}")
        assert response.status_code == 200
        issue_data = response.json()
        assert len(issue_data["photos"]) >= 1, "Photo should be attached to issue"
        print(f"Photo uploaded: {data['url']}")
    
    def test_20_upload_photo_nonexistent_issue(self):
        """Test uploading photo to non-existent issue returns 404"""
        import base64
        png_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )
        files = {"file": ("test.png", png_data, "image/png")}
        
        # Use session with cookies for file upload
        upload_session = requests.Session()
        upload_session.cookies = self.session.cookies
        upload_session.headers.update({"Authorization": f"Bearer {self.token}"})
        
        response = upload_session.post(
            f"{BASE_URL}/api/maintenance/upload-photo/nonexistent-id",
            files=files
        )
        assert response.status_code == 404
    
    # ==================== CLEANUP ====================
    
    def test_99_cleanup_test_data(self):
        """Cleanup test data created during tests"""
        # Delete test issues
        for attr in ['test_issue_id', 'critical_issue_id', 'low_issue_id']:
            issue_id = getattr(self.__class__, attr, None)
            if issue_id:
                try:
                    self.session.delete(f"{BASE_URL}/api/maintenance/issues/{issue_id}")
                except:
                    pass
        
        # Delete recurring schedules
        for attr in ['recurring_id', 'weekly_recurring_id']:
            schedule_id = getattr(self.__class__, attr, None)
            if schedule_id:
                try:
                    self.session.delete(f"{BASE_URL}/api/maintenance/recurring/{schedule_id}")
                except:
                    pass
        
        print("Test data cleanup completed")


class TestMaintenanceAutoAssignment:
    """Test auto-assignment rules for different categories"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_response.status_code == 200
        self.token = login_response.json().get("access_token")
        self.session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        })
        self.created_issues = []
        yield
        # Cleanup
        for issue_id in self.created_issues:
            try:
                self.session.delete(f"{BASE_URL}/api/maintenance/issues/{issue_id}")
            except:
                pass
    
    def test_cleaning_category_assigns_to_housekeeping(self):
        """Cleaning issues should auto-assign to housekeeping department"""
        response = self.session.post(f"{BASE_URL}/api/maintenance/issues", json={
            "property_id": TEST_PROPERTY,
            "title": f"TEST_Deep cleaning needed_{uuid.uuid4().hex[:6]}",
            "category": "cleaning",
            "priority": "medium"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["assigned_department"] == "housekeeping"
        self.created_issues.append(data["id"])
    
    def test_it_network_category_assigns_to_management(self):
        """IT/Network issues should auto-assign to management department"""
        response = self.session.post(f"{BASE_URL}/api/maintenance/issues", json={
            "property_id": TEST_PROPERTY,
            "title": f"TEST_WiFi router down_{uuid.uuid4().hex[:6]}",
            "category": "it_network",
            "priority": "high"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["assigned_department"] == "management"
        self.created_issues.append(data["id"])
    
    def test_electrical_category_assigns_to_maintenance(self):
        """Electrical issues should auto-assign to maintenance department"""
        response = self.session.post(f"{BASE_URL}/api/maintenance/issues", json={
            "property_id": TEST_PROPERTY,
            "title": f"TEST_Light fixture broken_{uuid.uuid4().hex[:6]}",
            "category": "electrical",
            "priority": "medium"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["assigned_department"] == "maintenance"
        self.created_issues.append(data["id"])


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
