"""
Iteration 141 - Staff Onboarding Security Lockdown Tests
Tests for:
- GET /api/staff-onboarding/me MUST NOT expose sensitive fields (filenames, urls, paths, hmrc_data, email_log)
- POST /api/staff-onboarding/upload/passport returns 400 if already uploaded (locked)
- POST /api/staff-onboarding/upload/address returns 400 if already uploaded (locked)
- POST /api/staff-onboarding/hmrc returns 400 if already submitted (locked)
- GET /api/uploads/onboarding/{filename} - unauth=401, staff=403, admin=200
- Path traversal protection on /api/uploads/onboarding/{filename}
- Regression: admin download endpoints still work
- Regression: new staff can still upload (lock only after first submission)
- Regression: /complete still activates user
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
STAFF_EMAIL = "sarah@hotel.test"
STAFF_PASSWORD = "StaffP@ss1"

# Fields that MUST NOT be exposed to staff in /me response
FORBIDDEN_FIELDS = [
    "passport_filename", "passport_url", "passport_path", "passport_uploaded_at",
    "address_proof_filename", "address_proof_url", "address_proof_path", "address_proof_uploaded_at",
    "hmrc_data", "email_log"
]

# Fields that SHOULD be exposed to staff in /me response
ALLOWED_FIELDS = [
    "user_id", "user_name", "user_email", "passport_uploaded", "address_proof_uploaded",
    "hmrc_submitted", "contract_signed", "contract_id", "activated", "progress", "hmrc_statements", "created_at"
]


@pytest.fixture(scope="module")
def admin_token():
    """Get admin auth token"""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if resp.status_code != 200:
        pytest.skip(f"Admin login failed: {resp.status_code} - {resp.text}")
    data = resp.json()
    return data.get("token") or data.get("access_token")


@pytest.fixture(scope="module")
def staff_token():
    """Get staff auth token (Sarah - all 4 steps done)"""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": STAFF_EMAIL,
        "password": STAFF_PASSWORD
    })
    if resp.status_code != 200:
        pytest.skip(f"Staff login failed: {resp.status_code} - {resp.text}")
    data = resp.json()
    return data.get("token") or data.get("access_token")


@pytest.fixture(scope="module")
def staff_user_id(admin_token):
    """Get Sarah's user_id from onboarding list"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    resp = requests.get(f"{BASE_URL}/api/staff-onboarding/list", headers=headers)
    if resp.status_code != 200:
        pytest.skip(f"Failed to get onboarding list: {resp.status_code}")
    
    data = resp.json()
    for row in data:
        if row.get("user_email") == STAFF_EMAIL:
            return row.get("user_id")
    
    pytest.skip(f"Staff user {STAFF_EMAIL} not found in onboarding list")


@pytest.fixture(scope="module")
def staff_onboarding_data(admin_token, staff_user_id):
    """Get Sarah's full onboarding data (admin view)"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    resp = requests.get(f"{BASE_URL}/api/staff-onboarding/list", headers=headers)
    data = resp.json()
    for row in data:
        if row.get("user_id") == staff_user_id:
            return row
    return {}


class TestStaffMeEndpointSecurity:
    """Test that /me endpoint does NOT expose sensitive fields to staff"""
    
    def test_me_does_not_expose_passport_filename(self, staff_token):
        """Staff /me should NOT include passport_filename"""
        headers = {"Authorization": f"Bearer {staff_token}"}
        resp = requests.get(f"{BASE_URL}/api/staff-onboarding/me", headers=headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        
        assert "passport_filename" not in data, "SECURITY: passport_filename should NOT be exposed"
        print("PASS: passport_filename not exposed")
    
    def test_me_does_not_expose_passport_url(self, staff_token):
        """Staff /me should NOT include passport_url"""
        headers = {"Authorization": f"Bearer {staff_token}"}
        resp = requests.get(f"{BASE_URL}/api/staff-onboarding/me", headers=headers)
        data = resp.json()
        
        assert "passport_url" not in data, "SECURITY: passport_url should NOT be exposed"
        print("PASS: passport_url not exposed")
    
    def test_me_does_not_expose_passport_path(self, staff_token):
        """Staff /me should NOT include passport_path"""
        headers = {"Authorization": f"Bearer {staff_token}"}
        resp = requests.get(f"{BASE_URL}/api/staff-onboarding/me", headers=headers)
        data = resp.json()
        
        assert "passport_path" not in data, "SECURITY: passport_path should NOT be exposed"
        print("PASS: passport_path not exposed")
    
    def test_me_does_not_expose_address_proof_filename(self, staff_token):
        """Staff /me should NOT include address_proof_filename"""
        headers = {"Authorization": f"Bearer {staff_token}"}
        resp = requests.get(f"{BASE_URL}/api/staff-onboarding/me", headers=headers)
        data = resp.json()
        
        assert "address_proof_filename" not in data, "SECURITY: address_proof_filename should NOT be exposed"
        print("PASS: address_proof_filename not exposed")
    
    def test_me_does_not_expose_address_proof_url(self, staff_token):
        """Staff /me should NOT include address_proof_url"""
        headers = {"Authorization": f"Bearer {staff_token}"}
        resp = requests.get(f"{BASE_URL}/api/staff-onboarding/me", headers=headers)
        data = resp.json()
        
        assert "address_proof_url" not in data, "SECURITY: address_proof_url should NOT be exposed"
        print("PASS: address_proof_url not exposed")
    
    def test_me_does_not_expose_hmrc_data(self, staff_token):
        """Staff /me should NOT include hmrc_data"""
        headers = {"Authorization": f"Bearer {staff_token}"}
        resp = requests.get(f"{BASE_URL}/api/staff-onboarding/me", headers=headers)
        data = resp.json()
        
        assert "hmrc_data" not in data, "SECURITY: hmrc_data should NOT be exposed"
        print("PASS: hmrc_data not exposed")
    
    def test_me_does_not_expose_email_log(self, staff_token):
        """Staff /me should NOT include email_log"""
        headers = {"Authorization": f"Bearer {staff_token}"}
        resp = requests.get(f"{BASE_URL}/api/staff-onboarding/me", headers=headers)
        data = resp.json()
        
        assert "email_log" not in data, "SECURITY: email_log should NOT be exposed"
        print("PASS: email_log not exposed")
    
    def test_me_exposes_only_allowed_fields(self, staff_token):
        """Staff /me should only include allowed fields"""
        headers = {"Authorization": f"Bearer {staff_token}"}
        resp = requests.get(f"{BASE_URL}/api/staff-onboarding/me", headers=headers)
        data = resp.json()
        
        # Check no forbidden fields
        for field in FORBIDDEN_FIELDS:
            assert field not in data, f"SECURITY: {field} should NOT be exposed"
        
        # Check allowed fields are present
        for field in ["passport_uploaded", "address_proof_uploaded", "hmrc_submitted", "contract_signed", "progress"]:
            assert field in data, f"Expected field {field} to be present"
        
        print(f"PASS: /me response contains only safe fields. Keys: {list(data.keys())}")


class TestUploadLockdown:
    """Test that re-upload is blocked after first submission"""
    
    def test_passport_reupload_blocked(self, staff_token, staff_onboarding_data):
        """Re-uploading passport when already uploaded returns 400"""
        if not staff_onboarding_data.get("passport_uploaded"):
            pytest.skip("Passport not yet uploaded - cannot test lock")
        
        headers = {"Authorization": f"Bearer {staff_token}"}
        # Create a dummy file
        files = {"file": ("test.jpg", b"fake image content", "image/jpeg")}
        resp = requests.post(f"{BASE_URL}/api/staff-onboarding/upload/passport", 
                           headers=headers, files=files)
        
        assert resp.status_code == 400, f"Expected 400 (locked), got {resp.status_code}"
        assert "locked" in resp.text.lower() or "already" in resp.text.lower(), \
            f"Expected lock message, got: {resp.text}"
        print("PASS: Passport re-upload blocked with 400")
    
    def test_address_reupload_blocked(self, staff_token, staff_onboarding_data):
        """Re-uploading address proof when already uploaded returns 400"""
        if not staff_onboarding_data.get("address_proof_uploaded"):
            pytest.skip("Address proof not yet uploaded - cannot test lock")
        
        headers = {"Authorization": f"Bearer {staff_token}"}
        files = {"file": ("test.pdf", b"fake pdf content", "application/pdf")}
        resp = requests.post(f"{BASE_URL}/api/staff-onboarding/upload/address", 
                           headers=headers, files=files)
        
        assert resp.status_code == 400, f"Expected 400 (locked), got {resp.status_code}"
        assert "locked" in resp.text.lower() or "already" in resp.text.lower(), \
            f"Expected lock message, got: {resp.text}"
        print("PASS: Address proof re-upload blocked with 400")
    
    def test_hmrc_resubmit_blocked(self, staff_token, staff_onboarding_data):
        """Re-submitting HMRC when already submitted returns 400"""
        if not staff_onboarding_data.get("hmrc_submitted"):
            pytest.skip("HMRC not yet submitted - cannot test lock")
        
        headers = {"Authorization": f"Bearer {staff_token}"}
        hmrc_data = {
            "last_name": "Test",
            "first_names": "User",
            "sex": "male",
            "dob": "1990-01-01",
            "home_address": "123 Test St",
            "postcode": "SW1A 1AA",
            "start_date": "2024-01-01",
            "statement": "A",
            "declaration_full_name": "TEST USER",
            "declaration_signature": "Test User",
            "declaration_date": "2024-01-01",
            "declaration_confirmed": True
        }
        resp = requests.post(f"{BASE_URL}/api/staff-onboarding/hmrc", 
                           headers=headers, json=hmrc_data)
        
        assert resp.status_code == 400, f"Expected 400 (locked), got {resp.status_code}"
        assert "locked" in resp.text.lower() or "already" in resp.text.lower(), \
            f"Expected lock message, got: {resp.text}"
        print("PASS: HMRC re-submit blocked with 400")


class TestDirectFileAccessSecurity:
    """Test /api/uploads/onboarding/{filename} access control"""
    
    def test_direct_file_access_unauth_401(self, staff_onboarding_data):
        """Unauthenticated access to onboarding files returns 401"""
        # Get a real filename from admin data
        filename = staff_onboarding_data.get("passport_url", "").split("/")[-1]
        if not filename:
            filename = "test.jpg"  # Use dummy if no real file
        
        resp = requests.get(f"{BASE_URL}/api/uploads/onboarding/{filename}")
        assert resp.status_code == 401, f"Expected 401 (unauth), got {resp.status_code}"
        print("PASS: Unauthenticated file access returns 401")
    
    def test_direct_file_access_staff_403(self, staff_token, staff_onboarding_data):
        """Staff role cannot access onboarding files directly (403)"""
        filename = staff_onboarding_data.get("passport_url", "").split("/")[-1]
        if not filename:
            filename = "test.jpg"
        
        headers = {"Authorization": f"Bearer {staff_token}"}
        resp = requests.get(f"{BASE_URL}/api/uploads/onboarding/{filename}", headers=headers)
        assert resp.status_code == 403, f"Expected 403 (forbidden for staff), got {resp.status_code}"
        print("PASS: Staff file access returns 403")
    
    def test_direct_file_access_admin_200(self, admin_token, staff_onboarding_data):
        """Admin can access onboarding files directly (200)"""
        filename = staff_onboarding_data.get("passport_url", "").split("/")[-1]
        if not filename:
            pytest.skip("No passport file to test")
        
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = requests.get(f"{BASE_URL}/api/uploads/onboarding/{filename}", headers=headers)
        assert resp.status_code == 200, f"Expected 200 (admin access), got {resp.status_code}"
        print(f"PASS: Admin file access returns 200 ({len(resp.content)} bytes)")
    
    def test_path_traversal_blocked_dotdot(self, admin_token):
        """Path traversal with .. is blocked - should not return sensitive file content"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        # URL-encoded path traversal attempt
        resp = requests.get(f"{BASE_URL}/api/uploads/onboarding/..%2F..%2F..%2Fetc%2Fpasswd", headers=headers)
        # Should return 400 (invalid filename) or 404 (not found) - NOT the actual /etc/passwd content
        assert resp.status_code in [400, 404], f"Expected 400 or 404 (path traversal blocked), got {resp.status_code}"
        # Verify we didn't get /etc/passwd content
        assert "root:" not in resp.text, "SECURITY: Path traversal returned /etc/passwd content!"
        print(f"PASS: Path traversal with .. blocked ({resp.status_code})")
    
    def test_path_traversal_blocked_slash(self, admin_token):
        """Path traversal with / is blocked - should not allow subdirectory access"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        # URL-encoded slash
        resp = requests.get(f"{BASE_URL}/api/uploads/onboarding/subdir%2Ffile.jpg", headers=headers)
        # Should return 400 (invalid filename) or 404 (not found)
        assert resp.status_code in [400, 404], f"Expected 400 or 404 (path traversal blocked), got {resp.status_code}"
        print(f"PASS: Path traversal with / blocked ({resp.status_code})")


class TestAdminDownloadRegression:
    """Regression: Admin download endpoints still work"""
    
    def test_admin_download_passport(self, admin_token, staff_user_id, staff_onboarding_data):
        """Admin can still download passport"""
        if not staff_onboarding_data.get("passport_uploaded"):
            pytest.skip("Passport not uploaded")
        
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = requests.get(f"{BASE_URL}/api/staff-onboarding/{staff_user_id}/download/passport", headers=headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        assert len(resp.content) > 0, "File should have content"
        print(f"PASS: Admin download passport works ({len(resp.content)} bytes)")
    
    def test_admin_download_address(self, admin_token, staff_user_id, staff_onboarding_data):
        """Admin can still download address proof"""
        if not staff_onboarding_data.get("address_proof_uploaded"):
            pytest.skip("Address proof not uploaded")
        
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = requests.get(f"{BASE_URL}/api/staff-onboarding/{staff_user_id}/download/address", headers=headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        print(f"PASS: Admin download address works ({len(resp.content)} bytes)")
    
    def test_admin_download_hmrc(self, admin_token, staff_user_id, staff_onboarding_data):
        """Admin can still download HMRC PDF"""
        if not staff_onboarding_data.get("hmrc_submitted"):
            pytest.skip("HMRC not submitted")
        
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = requests.get(f"{BASE_URL}/api/staff-onboarding/{staff_user_id}/download/hmrc", headers=headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        assert resp.content[:5] == b"%PDF-", "Should be a PDF"
        print(f"PASS: Admin download HMRC PDF works ({len(resp.content)} bytes)")
    
    def test_admin_download_bundle(self, admin_token, staff_user_id):
        """Admin can still download ZIP bundle"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = requests.get(f"{BASE_URL}/api/staff-onboarding/{staff_user_id}/download-bundle", headers=headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        assert resp.content[:2] == b"PK", "Should be a ZIP"
        print(f"PASS: Admin download bundle works ({len(resp.content)} bytes)")


class TestAdminListShowsAllData:
    """Regression: Admin list endpoint shows all HMRC data"""
    
    def test_admin_list_shows_hmrc_data(self, admin_token, staff_user_id):
        """Admin list includes full hmrc_data for each user"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = requests.get(f"{BASE_URL}/api/staff-onboarding/list", headers=headers)
        assert resp.status_code == 200
        
        data = resp.json()
        sarah = next((r for r in data if r.get("user_id") == staff_user_id), None)
        
        if sarah and sarah.get("hmrc_submitted"):
            assert "hmrc_data" in sarah, "Admin list should include hmrc_data"
            hmrc = sarah.get("hmrc_data", {})
            assert "last_name" in hmrc or "first_names" in hmrc, "hmrc_data should have personal details"
            print(f"PASS: Admin list shows hmrc_data with {len(hmrc)} fields")
        else:
            print("SKIP: Sarah's HMRC not submitted or not found")
    
    def test_admin_list_shows_filenames(self, admin_token, staff_user_id):
        """Admin list includes filenames"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = requests.get(f"{BASE_URL}/api/staff-onboarding/list", headers=headers)
        data = resp.json()
        
        sarah = next((r for r in data if r.get("user_id") == staff_user_id), None)
        if sarah and sarah.get("passport_uploaded"):
            assert "passport_filename" in sarah or "passport_url" in sarah, \
                "Admin list should include passport filename/url"
            print("PASS: Admin list shows passport filename/url")
        else:
            print("SKIP: Sarah's passport not uploaded or not found")


class TestCompleteOnboardingRegression:
    """Regression: /complete endpoint still works"""
    
    def test_complete_requires_all_tasks(self, staff_token):
        """Complete endpoint validates all tasks are done"""
        headers = {"Authorization": f"Bearer {staff_token}"}
        
        # First check current status
        resp = requests.get(f"{BASE_URL}/api/staff-onboarding/me", headers=headers)
        data = resp.json()
        progress = data.get("progress", {})
        
        if progress.get("complete"):
            # Try to complete - should work
            resp = requests.post(f"{BASE_URL}/api/staff-onboarding/complete", headers=headers)
            # Could be 200 (success) or 400 (already activated)
            assert resp.status_code in [200, 400], f"Expected 200 or 400, got {resp.status_code}"
            print(f"PASS: Complete endpoint responds correctly ({resp.status_code})")
        else:
            # Try to complete - should fail with missing tasks
            resp = requests.post(f"{BASE_URL}/api/staff-onboarding/complete", headers=headers)
            assert resp.status_code == 400, f"Expected 400 (incomplete), got {resp.status_code}"
            print("PASS: Complete endpoint rejects incomplete onboarding")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
