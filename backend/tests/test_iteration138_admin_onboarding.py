"""
Iteration 138 - Staff Onboarding Admin Panel Tests
Tests for admin-side review panel for staff onboarding:
- GET /api/staff-onboarding/list with filters
- POST /api/staff-onboarding/admin-activate/{user_id}
- POST /api/staff-onboarding/admin-deactivate/{user_id}
- Role gating (admin/manager only for list, admin only for activate/deactivate)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
STAFF_EMAIL = "sarah@hotel.test"
STAFF_PASSWORD = "StaffP@ss1"


class TestAdminOnboardingPanel:
    """Tests for admin onboarding review panel"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def login_as_admin(self):
        """Login as admin and return session"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        return response.json()
    
    def login_as_staff(self):
        """Login as staff user"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": STAFF_EMAIL,
            "password": STAFF_PASSWORD
        })
        assert response.status_code == 200, f"Staff login failed: {response.text}"
        return response.json()
    
    # ============ GET /api/staff-onboarding/list Tests ============
    
    def test_list_onboardings_as_admin(self):
        """Admin can list all staff onboarding records"""
        self.login_as_admin()
        response = self.session.get(f"{BASE_URL}/api/staff-onboarding/list")
        
        assert response.status_code == 200, f"List failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        
        # Verify structure of each record
        if len(data) > 0:
            record = data[0]
            assert "user_id" in record, "Record should have user_id"
            assert "user_name" in record, "Record should have user_name"
            assert "user_email" in record, "Record should have user_email"
            assert "progress" in record, "Record should have progress"
            assert "activated" in record, "Record should have activated status"
            
            # Verify progress structure
            progress = record["progress"]
            assert "tasks" in progress, "Progress should have tasks"
            assert "done" in progress, "Progress should have done count"
            assert "total" in progress, "Progress should have total count"
            assert "complete" in progress, "Progress should have complete flag"
            
            print(f"Found {len(data)} onboarding records")
            for r in data:
                print(f"  - {r.get('user_name')} ({r.get('user_email')}): {r.get('progress', {}).get('done')}/{r.get('progress', {}).get('total')}, activated={r.get('activated')}")
    
    def test_list_onboardings_filter_pending(self):
        """Filter list by pending (non-activated) status"""
        self.login_as_admin()
        response = self.session.get(f"{BASE_URL}/api/staff-onboarding/list?status=pending")
        
        assert response.status_code == 200
        data = response.json()
        
        # All records should be non-activated
        for record in data:
            assert record.get("activated") == False, f"Pending filter should only return non-activated users, got: {record}"
        
        print(f"Found {len(data)} pending (non-activated) records")
    
    def test_list_onboardings_filter_activated(self):
        """Filter list by activated status"""
        self.login_as_admin()
        response = self.session.get(f"{BASE_URL}/api/staff-onboarding/list?status=activated")
        
        assert response.status_code == 200
        data = response.json()
        
        # All records should be activated
        for record in data:
            assert record.get("activated") == True, f"Activated filter should only return activated users, got: {record}"
        
        print(f"Found {len(data)} activated records")
    
    def test_list_onboardings_filter_complete(self):
        """Filter list by complete (all docs done) status"""
        self.login_as_admin()
        response = self.session.get(f"{BASE_URL}/api/staff-onboarding/list?status=complete")
        
        assert response.status_code == 200
        data = response.json()
        
        # All records should have complete=true
        for record in data:
            assert record.get("progress", {}).get("complete") == True, f"Complete filter should only return complete records"
        
        print(f"Found {len(data)} complete records")
    
    def test_list_onboardings_filter_incomplete(self):
        """Filter list by incomplete status"""
        self.login_as_admin()
        response = self.session.get(f"{BASE_URL}/api/staff-onboarding/list?status=incomplete")
        
        assert response.status_code == 200
        data = response.json()
        
        # All records should have complete=false
        for record in data:
            assert record.get("progress", {}).get("complete") == False, f"Incomplete filter should only return incomplete records"
        
        print(f"Found {len(data)} incomplete records")
    
    # ============ Role Gating Tests ============
    
    def test_list_onboardings_rejected_for_receptionist(self):
        """Receptionist cannot access onboarding list"""
        self.login_as_staff()
        response = self.session.get(f"{BASE_URL}/api/staff-onboarding/list")
        
        # Should be 403 Forbidden
        assert response.status_code == 403, f"Expected 403 for receptionist, got {response.status_code}: {response.text}"
        print("Receptionist correctly denied access to onboarding list")
    
    def test_admin_activate_rejected_for_receptionist(self):
        """Receptionist cannot activate users"""
        self.login_as_staff()
        response = self.session.post(f"{BASE_URL}/api/staff-onboarding/admin-activate/some-user-id")
        
        # Should be 403 Forbidden
        assert response.status_code == 403, f"Expected 403 for receptionist, got {response.status_code}: {response.text}"
        print("Receptionist correctly denied access to admin-activate")
    
    def test_admin_deactivate_rejected_for_receptionist(self):
        """Receptionist cannot deactivate users"""
        self.login_as_staff()
        response = self.session.post(f"{BASE_URL}/api/staff-onboarding/admin-deactivate/some-user-id")
        
        # Should be 403 Forbidden
        assert response.status_code == 403, f"Expected 403 for receptionist, got {response.status_code}: {response.text}"
        print("Receptionist correctly denied access to admin-deactivate")
    
    # ============ Admin Activate/Deactivate Tests ============
    
    def test_admin_activate_user(self):
        """Admin can activate a user"""
        self.login_as_admin()
        
        # First get the list to find Sarah's user_id
        response = self.session.get(f"{BASE_URL}/api/staff-onboarding/list")
        assert response.status_code == 200
        data = response.json()
        
        # Find Sarah's record
        sarah_record = None
        for record in data:
            if record.get("user_email") == STAFF_EMAIL:
                sarah_record = record
                break
        
        if sarah_record is None:
            pytest.skip("Sarah's onboarding record not found - may need to be created first")
        
        user_id = sarah_record.get("user_id")
        print(f"Found Sarah's user_id: {user_id}")
        
        # Activate the user
        response = self.session.post(f"{BASE_URL}/api/staff-onboarding/admin-activate/{user_id}")
        assert response.status_code == 200, f"Activate failed: {response.text}"
        
        result = response.json()
        assert result.get("ok") == True, f"Expected ok=true, got: {result}"
        print(f"Successfully activated user {user_id}")
        
        # Verify activation by checking list again
        response = self.session.get(f"{BASE_URL}/api/staff-onboarding/list")
        data = response.json()
        
        for record in data:
            if record.get("user_id") == user_id:
                assert record.get("activated") == True, "User should now be activated"
                print(f"Verified: {record.get('user_name')} is now activated")
                break
    
    def test_admin_deactivate_user(self):
        """Admin can deactivate a user"""
        self.login_as_admin()
        
        # First get the list to find Sarah's user_id
        response = self.session.get(f"{BASE_URL}/api/staff-onboarding/list")
        assert response.status_code == 200
        data = response.json()
        
        # Find Sarah's record
        sarah_record = None
        for record in data:
            if record.get("user_email") == STAFF_EMAIL:
                sarah_record = record
                break
        
        if sarah_record is None:
            pytest.skip("Sarah's onboarding record not found")
        
        user_id = sarah_record.get("user_id")
        
        # Deactivate the user
        response = self.session.post(f"{BASE_URL}/api/staff-onboarding/admin-deactivate/{user_id}")
        assert response.status_code == 200, f"Deactivate failed: {response.text}"
        
        result = response.json()
        assert result.get("ok") == True, f"Expected ok=true, got: {result}"
        print(f"Successfully deactivated user {user_id}")
        
        # Verify deactivation by checking list again
        response = self.session.get(f"{BASE_URL}/api/staff-onboarding/list")
        data = response.json()
        
        for record in data:
            if record.get("user_id") == user_id:
                assert record.get("activated") == False, "User should now be deactivated"
                print(f"Verified: {record.get('user_name')} is now deactivated")
                break
    
    def test_admin_activate_nonexistent_user(self):
        """Activating non-existent user returns 404"""
        self.login_as_admin()
        
        response = self.session.post(f"{BASE_URL}/api/staff-onboarding/admin-activate/nonexistent-user-id-12345")
        assert response.status_code == 404, f"Expected 404 for non-existent user, got {response.status_code}"
        print("Correctly returned 404 for non-existent user")
    
    # ============ Data Verification Tests ============
    
    def test_onboarding_record_has_required_fields(self):
        """Verify onboarding records have all required fields for admin panel"""
        self.login_as_admin()
        response = self.session.get(f"{BASE_URL}/api/staff-onboarding/list")
        
        assert response.status_code == 200
        data = response.json()
        
        if len(data) == 0:
            pytest.skip("No onboarding records to verify")
        
        record = data[0]
        
        # Required fields for admin panel display
        required_fields = [
            "user_id", "user_name", "user_email", "user_role",
            "passport_uploaded", "address_proof_uploaded", 
            "hmrc_submitted", "contract_signed",
            "progress", "activated"
        ]
        
        for field in required_fields:
            assert field in record, f"Missing required field: {field}"
        
        # Progress should have task breakdown
        progress = record["progress"]
        assert "tasks" in progress
        assert "passport" in progress["tasks"]
        assert "address" in progress["tasks"]
        assert "hmrc" in progress["tasks"]
        assert "contract" in progress["tasks"]
        
        print(f"Record has all required fields: {list(record.keys())}")
    
    def test_onboarding_record_has_document_urls(self):
        """Verify records with uploaded docs have URLs for preview"""
        self.login_as_admin()
        response = self.session.get(f"{BASE_URL}/api/staff-onboarding/list")
        
        assert response.status_code == 200
        data = response.json()
        
        for record in data:
            if record.get("passport_uploaded"):
                assert "passport_url" in record, "Uploaded passport should have URL"
                print(f"  {record.get('user_name')}: passport_url = {record.get('passport_url')}")
            
            if record.get("address_proof_uploaded"):
                assert "address_proof_url" in record, "Uploaded address proof should have URL"
                print(f"  {record.get('user_name')}: address_proof_url = {record.get('address_proof_url')}")
            
            if record.get("hmrc_submitted"):
                assert "hmrc_data" in record, "Submitted HMRC should have data"
                hmrc = record.get("hmrc_data", {})
                print(f"  {record.get('user_name')}: HMRC data = {list(hmrc.keys())}")


class TestRegressionStaffOnboarding:
    """Regression tests for existing staff onboarding functionality"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def test_staff_onboarding_me_endpoint(self):
        """GET /api/staff-onboarding/me still works for staff users"""
        # Login as staff
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": STAFF_EMAIL,
            "password": STAFF_PASSWORD
        })
        assert response.status_code == 200
        
        # Get my onboarding status
        response = self.session.get(f"{BASE_URL}/api/staff-onboarding/me")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "progress" in data
        assert "hmrc_statements" in data
        print(f"Staff onboarding/me works: progress={data.get('progress')}")
    
    def test_auth_returns_is_activated(self):
        """Auth endpoints return is_activated field"""
        # Login
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        
        assert "is_activated" in data, "Login should return is_activated"
        print(f"Login returns is_activated={data.get('is_activated')}")
        
        # Get me
        response = self.session.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 200
        data = response.json()
        
        assert "is_activated" in data, "Auth/me should return is_activated"
        print(f"Auth/me returns is_activated={data.get('is_activated')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
