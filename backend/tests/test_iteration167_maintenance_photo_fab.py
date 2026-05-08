"""
Iteration 167 - Maintenance Photo Upload + FAB Language Toggle Tests
Tests:
1. Housekeeper can create maintenance issues
2. Housekeeper can upload photos to maintenance issues (role fix verification)
3. Multiple photos can be uploaded (up to 3)
4. photos_before array is correctly populated
5. Admin can also upload photos
"""
import pytest
import requests
import os
import base64

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
HK_EMAIL = "testhk@hotelbox.com"
HK_PASSWORD = "Test2026!"
PROPERTY_ID = "aldgate-flats"


class TestMaintenancePhotoUpload:
    """Test maintenance photo upload functionality including housekeeper role fix"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.created_issues = []
    
    def get_auth_token(self, email, password):
        """Get authentication token"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": email,
            "password": password
        })
        if response.status_code == 200:
            return response.json().get("token")
        return None
    
    def test_01_admin_login(self):
        """Test admin can login"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["role"] == "admin"
        print(f"✓ Admin login successful: {data['email']}")
    
    def test_02_housekeeper_login(self):
        """Test housekeeper can login"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": HK_EMAIL,
            "password": HK_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["role"] == "housekeeper"
        print(f"✓ Housekeeper login successful: {data['email']}")
    
    def test_03_housekeeper_can_create_issue(self):
        """Test housekeeper can create maintenance issue"""
        token = self.get_auth_token(HK_EMAIL, HK_PASSWORD)
        assert token, "Failed to get housekeeper token"
        
        response = requests.post(
            f"{BASE_URL}/api/maintenance/issues",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "property_id": PROPERTY_ID,
                "title": "TEST_HK_Create_Issue_167",
                "description": "Testing housekeeper can create issues",
                "category": "cleaning",
                "priority": "medium",
                "location": "Room 102"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["status"] == "open"
        assert data["reported_by"] == "Test Housekeeper"
        self.created_issues.append(data["id"])
        print(f"✓ Housekeeper created issue: {data['id']}")
    
    def test_04_housekeeper_can_upload_photo(self):
        """Test housekeeper can upload photo to maintenance issue (ROLE FIX VERIFICATION)"""
        token = self.get_auth_token(HK_EMAIL, HK_PASSWORD)
        assert token, "Failed to get housekeeper token"
        
        # Create issue first
        create_response = requests.post(
            f"{BASE_URL}/api/maintenance/issues",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "property_id": PROPERTY_ID,
                "title": "TEST_HK_Photo_Upload_167",
                "description": "Testing housekeeper photo upload",
                "category": "cleaning",
                "priority": "high"
            }
        )
        assert create_response.status_code == 200
        issue_id = create_response.json()["id"]
        
        # Create a minimal PNG image
        png_data = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
        
        # Upload photo as housekeeper
        upload_response = requests.post(
            f"{BASE_URL}/api/maintenance/upload-photo/{issue_id}",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("test_hk_photo.png", png_data, "image/png")},
            data={"photo_type": "before"}
        )
        
        # This is the key test - housekeeper should now be able to upload (was 403 before fix)
        assert upload_response.status_code == 200, f"Housekeeper photo upload failed: {upload_response.text}"
        data = upload_response.json()
        assert data["status"] == "uploaded"
        assert data["type"] == "before"
        assert "/api/uploads/maintenance/" in data["url"]
        print(f"✓ Housekeeper uploaded photo successfully: {data['url']}")
        
        # Verify photo is in photos_before array
        detail_response = requests.get(
            f"{BASE_URL}/api/maintenance/issues/detail/{issue_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert detail_response.status_code == 200
        issue_data = detail_response.json()
        assert len(issue_data["photos_before"]) == 1
        assert issue_data["photos_before"][0]["uploaded_by"] == "Test Housekeeper"
        print(f"✓ Photo verified in photos_before array")
    
    def test_05_multiple_photos_upload(self):
        """Test multiple photos can be uploaded to an issue"""
        token = self.get_auth_token(ADMIN_EMAIL, ADMIN_PASSWORD)
        assert token, "Failed to get admin token"
        
        # Create issue
        create_response = requests.post(
            f"{BASE_URL}/api/maintenance/issues",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "property_id": PROPERTY_ID,
                "title": "TEST_Multi_Photo_167",
                "description": "Testing multiple photo upload",
                "category": "plumbing",
                "priority": "high"
            }
        )
        assert create_response.status_code == 200
        issue_id = create_response.json()["id"]
        
        # Upload 3 photos
        png_data = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
        
        for i in range(3):
            upload_response = requests.post(
                f"{BASE_URL}/api/maintenance/upload-photo/{issue_id}",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": (f"photo_{i+1}.png", png_data, "image/png")},
                data={"photo_type": "before"}
            )
            assert upload_response.status_code == 200
            print(f"✓ Uploaded photo {i+1}/3")
        
        # Verify all 3 photos are in photos_before
        detail_response = requests.get(
            f"{BASE_URL}/api/maintenance/issues/detail/{issue_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert detail_response.status_code == 200
        issue_data = detail_response.json()
        assert len(issue_data["photos_before"]) == 3
        print(f"✓ All 3 photos verified in photos_before array")
    
    def test_06_admin_can_upload_photo(self):
        """Test admin can upload photo (regression test)"""
        token = self.get_auth_token(ADMIN_EMAIL, ADMIN_PASSWORD)
        assert token, "Failed to get admin token"
        
        # Create issue
        create_response = requests.post(
            f"{BASE_URL}/api/maintenance/issues",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "property_id": PROPERTY_ID,
                "title": "TEST_Admin_Photo_167",
                "description": "Testing admin photo upload",
                "category": "electrical",
                "priority": "critical"
            }
        )
        assert create_response.status_code == 200
        issue_id = create_response.json()["id"]
        
        # Upload photo
        png_data = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
        
        upload_response = requests.post(
            f"{BASE_URL}/api/maintenance/upload-photo/{issue_id}",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("admin_photo.png", png_data, "image/png")},
            data={"photo_type": "before"}
        )
        assert upload_response.status_code == 200
        data = upload_response.json()
        assert data["status"] == "uploaded"
        print(f"✓ Admin uploaded photo successfully")
    
    def test_07_after_photo_upload(self):
        """Test 'after' photo type upload"""
        token = self.get_auth_token(ADMIN_EMAIL, ADMIN_PASSWORD)
        assert token, "Failed to get admin token"
        
        # Create issue
        create_response = requests.post(
            f"{BASE_URL}/api/maintenance/issues",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "property_id": PROPERTY_ID,
                "title": "TEST_After_Photo_167",
                "description": "Testing after photo upload",
                "category": "furniture",
                "priority": "low"
            }
        )
        assert create_response.status_code == 200
        issue_id = create_response.json()["id"]
        
        # Upload 'after' photo
        png_data = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
        
        upload_response = requests.post(
            f"{BASE_URL}/api/maintenance/upload-photo/{issue_id}",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("after_photo.png", png_data, "image/png")},
            data={"photo_type": "after"}
        )
        assert upload_response.status_code == 200
        data = upload_response.json()
        assert data["type"] == "after"
        
        # Verify in photos_after array
        detail_response = requests.get(
            f"{BASE_URL}/api/maintenance/issues/detail/{issue_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert detail_response.status_code == 200
        issue_data = detail_response.json()
        assert len(issue_data["photos_after"]) == 1
        print(f"✓ After photo verified in photos_after array")
    
    def test_08_list_issues_with_photos(self):
        """Test listing issues returns photo arrays"""
        token = self.get_auth_token(ADMIN_EMAIL, ADMIN_PASSWORD)
        assert token, "Failed to get admin token"
        
        response = requests.get(
            f"{BASE_URL}/api/maintenance/issues/{PROPERTY_ID}",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        issues = response.json()
        assert isinstance(issues, list)
        
        # Find our test issues with photos
        test_issues = [i for i in issues if "TEST_" in (i.get("title") or "")]
        photo_issues = [i for i in test_issues if len(i.get("photos_before", [])) > 0 or len(i.get("photos_after", [])) > 0]
        
        print(f"✓ Found {len(photo_issues)} test issues with photos")
        assert len(photo_issues) > 0, "Should have at least one issue with photos"
    
    def test_09_housekeeper_list_issues(self):
        """Test housekeeper can list maintenance issues"""
        token = self.get_auth_token(HK_EMAIL, HK_PASSWORD)
        assert token, "Failed to get housekeeper token"
        
        response = requests.get(
            f"{BASE_URL}/api/maintenance/issues/{PROPERTY_ID}",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        issues = response.json()
        assert isinstance(issues, list)
        print(f"✓ Housekeeper can list {len(issues)} issues")
    
    def test_10_upload_to_nonexistent_issue(self):
        """Test upload to non-existent issue returns 404"""
        token = self.get_auth_token(ADMIN_EMAIL, ADMIN_PASSWORD)
        assert token, "Failed to get admin token"
        
        png_data = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
        
        upload_response = requests.post(
            f"{BASE_URL}/api/maintenance/upload-photo/nonexistent-issue-id",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("test.png", png_data, "image/png")},
            data={"photo_type": "before"}
        )
        assert upload_response.status_code == 404
        print(f"✓ Upload to non-existent issue correctly returns 404")


class TestMaintenanceStats:
    """Test maintenance stats endpoint"""
    
    def test_stats_endpoint(self):
        """Test stats endpoint returns expected data"""
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json().get("token")
        
        stats_response = requests.get(
            f"{BASE_URL}/api/maintenance/stats/{PROPERTY_ID}",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert stats_response.status_code == 200
        data = stats_response.json()
        
        # Verify expected fields
        assert "total" in data
        assert "open" in data
        assert "in_progress" in data
        assert "resolved" in data
        assert "overdue" in data
        assert "by_category" in data
        assert "by_priority" in data
        print(f"✓ Stats endpoint returns expected data: {data['total']} total issues")


class TestCleanup:
    """Cleanup test data"""
    
    def test_cleanup_test_issues(self):
        """Delete test issues created during testing"""
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json().get("token")
        
        # Get all issues
        issues_response = requests.get(
            f"{BASE_URL}/api/maintenance/issues/{PROPERTY_ID}",
            headers={"Authorization": f"Bearer {token}"}
        )
        issues = issues_response.json()
        
        # Delete test issues
        deleted = 0
        for issue in issues:
            if issue.get("title", "").startswith("TEST_"):
                delete_response = requests.delete(
                    f"{BASE_URL}/api/maintenance/issues/{issue['id']}",
                    headers={"Authorization": f"Bearer {token}"}
                )
                if delete_response.status_code == 200:
                    deleted += 1
        
        print(f"✓ Cleaned up {deleted} test issues")
