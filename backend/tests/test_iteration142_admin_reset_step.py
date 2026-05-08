"""
Iteration 142 - Admin Reset Step Tests
Tests for POST /api/staff-onboarding/{user_id}/reset/{kind}
- Admin-only access (403 for manager/staff)
- Reset passport: deletes file, unsets fields, flips passport_uploaded=false
- Reset address: same for address_proof_* fields
- Reset hmrc: unsets hmrc_data, flips hmrc_submitted=false
- Reset contract: unsets contract_id, flips contract_signed=false
- Unknown kind returns 400
- Audit trail: reset_log entries
- Staff can re-upload after reset
"""
import pytest
import requests
import os
import io

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
STAFF_EMAIL = "sarah@hotel.test"
STAFF_PASSWORD = "StaffP@ss1"


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
    """Get staff authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": STAFF_EMAIL,
        "password": STAFF_PASSWORD
    })
    assert response.status_code == 200, f"Staff login failed: {response.text}"
    return response.json()


@pytest.fixture(scope="module")
def sarah_user_id(admin_token):
    """Get Sarah's user_id from onboarding list"""
    response = requests.get(
        f"{BASE_URL}/api/staff-onboarding/list",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    sarah = next((d for d in data if d.get("user_email") == STAFF_EMAIL), None)
    assert sarah is not None, "Sarah's onboarding record not found"
    return sarah["user_id"]


class TestResetEndpointAccess:
    """Test access control for reset endpoint"""
    
    def test_reset_requires_admin_role(self, staff_token, sarah_user_id):
        """Staff role should get 403 when trying to reset"""
        response = requests.post(
            f"{BASE_URL}/api/staff-onboarding/{sarah_user_id}/reset/passport",
            headers={"Authorization": f"Bearer {staff_token['token']}"}
        )
        assert response.status_code == 403, f"Expected 403 for staff, got {response.status_code}"
        print("PASS: Staff role gets 403 on reset endpoint")
    
    def test_reset_without_auth_returns_401(self, sarah_user_id):
        """No auth should return 401"""
        response = requests.post(
            f"{BASE_URL}/api/staff-onboarding/{sarah_user_id}/reset/passport"
        )
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"
        print("PASS: No auth returns 401")
    
    def test_reset_unknown_kind_returns_400(self, admin_token, sarah_user_id):
        """Unknown step kind should return 400"""
        response = requests.post(
            f"{BASE_URL}/api/staff-onboarding/{sarah_user_id}/reset/unknown_step",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 400, f"Expected 400 for unknown kind, got {response.status_code}"
        data = response.json()
        assert "Unknown step" in data.get("detail", ""), f"Expected 'Unknown step' in error, got {data}"
        print("PASS: Unknown step kind returns 400 'Unknown step'")
    
    def test_reset_nonexistent_user_returns_404(self, admin_token):
        """Reset for non-existent user should return 404"""
        response = requests.post(
            f"{BASE_URL}/api/staff-onboarding/nonexistent-user-id/reset/passport",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 404, f"Expected 404 for nonexistent user, got {response.status_code}"
        print("PASS: Nonexistent user returns 404")


class TestResetPassport:
    """Test passport reset functionality"""
    
    def test_reset_passport_success(self, admin_token, sarah_user_id):
        """Admin can reset passport step"""
        # First check current state
        list_resp = requests.get(
            f"{BASE_URL}/api/staff-onboarding/list",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        sarah_before = next((d for d in list_resp.json() if d["user_id"] == sarah_user_id), None)
        
        # Reset passport
        response = requests.post(
            f"{BASE_URL}/api/staff-onboarding/{sarah_user_id}/reset/passport",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Reset passport failed: {response.text}"
        data = response.json()
        assert data.get("ok") is True
        assert data.get("step") == "passport"
        print("PASS: Reset passport returns 200 with ok=true, step=passport")
        
        # Verify state changed
        list_resp = requests.get(
            f"{BASE_URL}/api/staff-onboarding/list",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        sarah_after = next((d for d in list_resp.json() if d["user_id"] == sarah_user_id), None)
        assert sarah_after["passport_uploaded"] is False, "passport_uploaded should be False after reset"
        print("PASS: passport_uploaded is False after reset")
    
    def test_staff_can_reupload_passport_after_reset(self, admin_token, staff_token, sarah_user_id):
        """After reset, staff can upload passport again"""
        # Ensure passport is reset
        requests.post(
            f"{BASE_URL}/api/staff-onboarding/{sarah_user_id}/reset/passport",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        # Staff uploads new passport
        files = {"file": ("new_passport.jpg", b"fake image content for test", "image/jpeg")}
        response = requests.post(
            f"{BASE_URL}/api/staff-onboarding/upload/passport",
            headers={"Authorization": f"Bearer {staff_token['token']}"},
            files=files
        )
        assert response.status_code == 200, f"Re-upload failed: {response.text}"
        data = response.json()
        assert data.get("ok") is True
        print("PASS: Staff can re-upload passport after admin reset")


class TestResetAddress:
    """Test address proof reset functionality"""
    
    def test_reset_address_success(self, admin_token, sarah_user_id):
        """Admin can reset address step"""
        response = requests.post(
            f"{BASE_URL}/api/staff-onboarding/{sarah_user_id}/reset/address",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Reset address failed: {response.text}"
        data = response.json()
        assert data.get("ok") is True
        assert data.get("step") == "address"
        print("PASS: Reset address returns 200 with ok=true, step=address")
        
        # Verify state changed
        list_resp = requests.get(
            f"{BASE_URL}/api/staff-onboarding/list",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        sarah_after = next((d for d in list_resp.json() if d["user_id"] == sarah_user_id), None)
        assert sarah_after["address_proof_uploaded"] is False, "address_proof_uploaded should be False after reset"
        print("PASS: address_proof_uploaded is False after reset")
    
    def test_staff_can_reupload_address_after_reset(self, admin_token, staff_token, sarah_user_id):
        """After reset, staff can upload address proof again"""
        # Ensure address is reset
        requests.post(
            f"{BASE_URL}/api/staff-onboarding/{sarah_user_id}/reset/address",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        # Staff uploads new address proof
        files = {"file": ("new_bill.pdf", b"fake pdf content for test", "application/pdf")}
        response = requests.post(
            f"{BASE_URL}/api/staff-onboarding/upload/address",
            headers={"Authorization": f"Bearer {staff_token['token']}"},
            files=files
        )
        assert response.status_code == 200, f"Re-upload failed: {response.text}"
        data = response.json()
        assert data.get("ok") is True
        print("PASS: Staff can re-upload address proof after admin reset")


class TestResetHmrc:
    """Test HMRC checklist reset functionality"""
    
    def test_reset_hmrc_success(self, admin_token, sarah_user_id):
        """Admin can reset HMRC step"""
        response = requests.post(
            f"{BASE_URL}/api/staff-onboarding/{sarah_user_id}/reset/hmrc",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Reset HMRC failed: {response.text}"
        data = response.json()
        assert data.get("ok") is True
        assert data.get("step") == "hmrc"
        print("PASS: Reset HMRC returns 200 with ok=true, step=hmrc")
        
        # Verify state changed
        list_resp = requests.get(
            f"{BASE_URL}/api/staff-onboarding/list",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        sarah_after = next((d for d in list_resp.json() if d["user_id"] == sarah_user_id), None)
        assert sarah_after["hmrc_submitted"] is False, "hmrc_submitted should be False after reset"
        print("PASS: hmrc_submitted is False after reset")
    
    def test_staff_can_resubmit_hmrc_after_reset(self, admin_token, staff_token, sarah_user_id):
        """After reset, staff can submit HMRC checklist again"""
        # Ensure HMRC is reset
        requests.post(
            f"{BASE_URL}/api/staff-onboarding/{sarah_user_id}/reset/hmrc",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        # Staff submits new HMRC data
        hmrc_data = {
            "last_name": "Tester",
            "first_names": "Sarah",
            "sex": "female",
            "dob": "1990-05-15",
            "home_address": "123 Test Street, London",
            "postcode": "SW1A 1AA",
            "start_date": "2026-01-15",
            "statement": "A",
            "declaration_full_name": "Sarah Tester",
            "declaration_signature": "Sarah Tester",
            "declaration_date": "2026-01-18",
            "declaration_confirmed": True
        }
        response = requests.post(
            f"{BASE_URL}/api/staff-onboarding/hmrc",
            headers={"Authorization": f"Bearer {staff_token['token']}"},
            json=hmrc_data
        )
        assert response.status_code == 200, f"Re-submit HMRC failed: {response.text}"
        data = response.json()
        assert data.get("ok") is True
        print("PASS: Staff can re-submit HMRC checklist after admin reset")


class TestResetContract:
    """Test contract reset functionality"""
    
    def test_reset_contract_success(self, admin_token, sarah_user_id):
        """Admin can reset contract step"""
        response = requests.post(
            f"{BASE_URL}/api/staff-onboarding/{sarah_user_id}/reset/contract",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Reset contract failed: {response.text}"
        data = response.json()
        assert data.get("ok") is True
        assert data.get("step") == "contract"
        print("PASS: Reset contract returns 200 with ok=true, step=contract")
        
        # Verify state changed
        list_resp = requests.get(
            f"{BASE_URL}/api/staff-onboarding/list",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        sarah_after = next((d for d in list_resp.json() if d["user_id"] == sarah_user_id), None)
        assert sarah_after["contract_signed"] is False, "contract_signed should be False after reset"
        print("PASS: contract_signed is False after reset")


class TestResetAuditTrail:
    """Test audit trail (reset_log) functionality"""
    
    def test_reset_creates_audit_log_entry(self, admin_token, sarah_user_id):
        """Each reset should append to reset_log"""
        # Get current reset_log count
        list_resp = requests.get(
            f"{BASE_URL}/api/staff-onboarding/list",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        sarah_before = next((d for d in list_resp.json() if d["user_id"] == sarah_user_id), None)
        log_count_before = len(sarah_before.get("reset_log", []))
        
        # Reset passport
        requests.post(
            f"{BASE_URL}/api/staff-onboarding/{sarah_user_id}/reset/passport",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        # Check reset_log increased
        list_resp = requests.get(
            f"{BASE_URL}/api/staff-onboarding/list",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        sarah_after = next((d for d in list_resp.json() if d["user_id"] == sarah_user_id), None)
        log_count_after = len(sarah_after.get("reset_log", []))
        
        assert log_count_after > log_count_before, "reset_log should have new entry"
        
        # Check latest entry structure
        latest_entry = sarah_after["reset_log"][-1]
        assert "step" in latest_entry, "reset_log entry should have 'step'"
        assert "reset_by" in latest_entry, "reset_log entry should have 'reset_by'"
        assert "reset_at" in latest_entry, "reset_log entry should have 'reset_at'"
        assert latest_entry["step"] == "passport"
        print("PASS: Reset creates audit log entry with step, reset_by, reset_at")
    
    def test_admin_list_returns_reset_log(self, admin_token, sarah_user_id):
        """Admin list endpoint should include reset_log"""
        list_resp = requests.get(
            f"{BASE_URL}/api/staff-onboarding/list",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert list_resp.status_code == 200
        sarah = next((d for d in list_resp.json() if d["user_id"] == sarah_user_id), None)
        assert "reset_log" in sarah, "Admin list should include reset_log"
        assert isinstance(sarah["reset_log"], list), "reset_log should be a list"
        print("PASS: Admin list endpoint returns reset_log entries")


class TestRegressionDownloadBundleEmail:
    """Regression tests for download, bundle, and email functionality"""
    
    def test_download_passport_still_works(self, admin_token, sarah_user_id):
        """Download passport should still work after reset tests"""
        # First ensure passport is uploaded
        list_resp = requests.get(
            f"{BASE_URL}/api/staff-onboarding/list",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        sarah = next((d for d in list_resp.json() if d["user_id"] == sarah_user_id), None)
        
        if sarah.get("passport_uploaded"):
            response = requests.get(
                f"{BASE_URL}/api/staff-onboarding/{sarah_user_id}/download/passport",
                headers={"Authorization": f"Bearer {admin_token}"}
            )
            assert response.status_code == 200, f"Download passport failed: {response.status_code}"
            print("PASS: Download passport still works")
        else:
            print("SKIP: Passport not uploaded, skipping download test")
    
    def test_download_bundle_still_works(self, admin_token, sarah_user_id):
        """Download bundle should still work"""
        response = requests.get(
            f"{BASE_URL}/api/staff-onboarding/{sarah_user_id}/download-bundle",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Download bundle failed: {response.status_code}"
        assert response.headers.get("content-type", "").startswith("application/zip")
        print("PASS: Download bundle still works")


class TestValidKinds:
    """Test all valid reset kinds"""
    
    @pytest.mark.parametrize("kind", ["passport", "address", "hmrc", "contract"])
    def test_valid_kinds_accepted(self, admin_token, sarah_user_id, kind):
        """All valid kinds should be accepted"""
        response = requests.post(
            f"{BASE_URL}/api/staff-onboarding/{sarah_user_id}/reset/{kind}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Reset {kind} failed: {response.text}"
        data = response.json()
        assert data.get("ok") is True
        assert data.get("step") == kind
        print(f"PASS: Reset {kind} accepted")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
