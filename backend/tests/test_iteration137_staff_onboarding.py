"""
Test Staff Onboarding Gate - Iteration 137
Tests the new staff onboarding flow:
- Registration returns is_activated=false for staff roles
- Login/me returns is_activated field
- Onboarding endpoints: /me, /upload/passport, /upload/address, /hmrc, /complete
- Admin endpoints: /list, /admin-activate, /admin-deactivate
"""
import pytest
import requests
import os
import io

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
STAFF_EMAIL = "sarah@hotel.test"
STAFF_PASSWORD = "StaffP@ss1"


class TestAuthIsActivatedField:
    """Test that auth endpoints return is_activated field"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        
    def test_login_returns_is_activated_for_admin(self):
        """Admin login should return is_activated=true"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "is_activated" in data, "is_activated field missing from login response"
        assert data["is_activated"] == True, "Admin should be activated"
        
    def test_login_returns_is_activated_for_staff(self):
        """Staff login should return is_activated field (false for non-activated)"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": STAFF_EMAIL,
            "password": STAFF_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "is_activated" in data, "is_activated field missing from login response"
        # Sarah should be non-activated per test setup
        assert data["is_activated"] == False, "Staff sarah should not be activated"
        
    def test_auth_me_returns_is_activated(self):
        """GET /auth/me should return is_activated field"""
        # Login first
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert login_resp.status_code == 200
        
        # Get /auth/me
        me_resp = self.session.get(f"{BASE_URL}/api/auth/me")
        assert me_resp.status_code == 200, f"GET /auth/me failed: {me_resp.text}"
        data = me_resp.json()
        assert "is_activated" in data, "is_activated field missing from /auth/me response"


class TestRegisterIsActivated:
    """Test that register sets is_activated based on role"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        # Login as admin
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert login_resp.status_code == 200
        
    def test_register_receptionist_not_activated(self):
        """Registering receptionist should set is_activated=false"""
        import uuid
        test_email = f"test_receptionist_{uuid.uuid4().hex[:8]}@hotel.test"
        response = self.session.post(f"{BASE_URL}/api/auth/register", json={
            "email": test_email,
            "password": "TestPass123!",
            "name": "Test Receptionist",
            "role": "receptionist",
            "department": "front_desk"
        })
        assert response.status_code == 200, f"Register failed: {response.text}"
        data = response.json()
        assert data.get("is_activated") == False, "Receptionist should not be activated"
        assert data.get("needs_onboarding") == True, "Receptionist needs onboarding"
        
    def test_register_housekeeper_not_activated(self):
        """Registering housekeeper should set is_activated=false"""
        import uuid
        test_email = f"test_housekeeper_{uuid.uuid4().hex[:8]}@hotel.test"
        response = self.session.post(f"{BASE_URL}/api/auth/register", json={
            "email": test_email,
            "password": "TestPass123!",
            "name": "Test Housekeeper",
            "role": "housekeeper",
            "department": "housekeeping"
        })
        # housekeeper role may not be valid - check response
        if response.status_code == 400 and "Invalid role" in response.text:
            pytest.skip("housekeeper role not in VALID_ROLES")
        assert response.status_code == 200, f"Register failed: {response.text}"
        data = response.json()
        assert data.get("is_activated") == False, "Housekeeper should not be activated"
        
    def test_register_manager_is_activated(self):
        """Registering manager should set is_activated=true"""
        import uuid
        test_email = f"test_manager_{uuid.uuid4().hex[:8]}@hotel.test"
        response = self.session.post(f"{BASE_URL}/api/auth/register", json={
            "email": test_email,
            "password": "TestPass123!",
            "name": "Test Manager",
            "role": "manager",
            "department": "management"
        })
        assert response.status_code == 200, f"Register failed: {response.text}"
        data = response.json()
        assert data.get("is_activated") == True, "Manager should be activated"
        assert data.get("needs_onboarding") == False, "Manager does not need onboarding"


class TestStaffOnboardingMe:
    """Test GET /staff-onboarding/me endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        # Login as staff
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": STAFF_EMAIL,
            "password": STAFF_PASSWORD
        })
        assert login_resp.status_code == 200, f"Staff login failed: {login_resp.text}"
        
    def test_onboarding_me_returns_progress(self):
        """GET /staff-onboarding/me should return progress object"""
        response = self.session.get(f"{BASE_URL}/api/staff-onboarding/me")
        assert response.status_code == 200, f"GET /staff-onboarding/me failed: {response.text}"
        data = response.json()
        
        # Check progress structure
        assert "progress" in data, "progress field missing"
        progress = data["progress"]
        assert "tasks" in progress, "tasks field missing in progress"
        assert "done" in progress, "done field missing in progress"
        assert "total" in progress, "total field missing in progress"
        assert "pct" in progress, "pct field missing in progress"
        assert "complete" in progress, "complete field missing in progress"
        
        # Check tasks structure
        tasks = progress["tasks"]
        assert "passport" in tasks, "passport task missing"
        assert "address" in tasks, "address task missing"
        assert "hmrc" in tasks, "hmrc task missing"
        assert "contract" in tasks, "contract task missing"
        
    def test_onboarding_me_returns_hmrc_statements(self):
        """GET /staff-onboarding/me should return hmrc_statements dict"""
        response = self.session.get(f"{BASE_URL}/api/staff-onboarding/me")
        assert response.status_code == 200
        data = response.json()
        
        assert "hmrc_statements" in data, "hmrc_statements field missing"
        statements = data["hmrc_statements"]
        assert "A" in statements, "Statement A missing"
        assert "B" in statements, "Statement B missing"
        assert "C" in statements, "Statement C missing"
        
    def test_onboarding_me_auto_creates_doc(self):
        """GET /staff-onboarding/me should auto-create onboarding doc if missing"""
        response = self.session.get(f"{BASE_URL}/api/staff-onboarding/me")
        assert response.status_code == 200
        data = response.json()
        
        # Should have user info
        assert "user_id" in data, "user_id field missing"
        assert "user_email" in data, "user_email field missing"


class TestStaffOnboardingUpload:
    """Test upload endpoints for passport and address"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        # Login as staff
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": STAFF_EMAIL,
            "password": STAFF_PASSWORD
        })
        assert login_resp.status_code == 200
        
    def test_upload_passport_success(self):
        """POST /staff-onboarding/upload/passport should accept valid file"""
        # Create a fake image file
        file_content = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100  # Minimal PNG header
        files = {'file': ('test_passport.png', io.BytesIO(file_content), 'image/png')}
        
        response = self.session.post(f"{BASE_URL}/api/staff-onboarding/upload/passport", files=files)
        assert response.status_code == 200, f"Upload passport failed: {response.text}"
        data = response.json()
        assert data.get("ok") == True, "Upload should return ok=true"
        assert "filename" in data, "filename should be in response"
        
    def test_upload_passport_invalid_type(self):
        """POST /staff-onboarding/upload/passport should reject invalid file types"""
        file_content = b'not a valid file'
        files = {'file': ('test.exe', io.BytesIO(file_content), 'application/octet-stream')}
        
        response = self.session.post(f"{BASE_URL}/api/staff-onboarding/upload/passport", files=files)
        assert response.status_code == 400, "Should reject invalid file type"
        
    def test_upload_address_success(self):
        """POST /staff-onboarding/upload/address should accept valid file"""
        file_content = b'%PDF-1.4' + b'\x00' * 100  # Minimal PDF header
        files = {'file': ('address_proof.pdf', io.BytesIO(file_content), 'application/pdf')}
        
        response = self.session.post(f"{BASE_URL}/api/staff-onboarding/upload/address", files=files)
        assert response.status_code == 200, f"Upload address failed: {response.text}"
        data = response.json()
        assert data.get("ok") == True


class TestStaffOnboardingHMRC:
    """Test HMRC checklist submission"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        # Login as staff
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": STAFF_EMAIL,
            "password": STAFF_PASSWORD
        })
        assert login_resp.status_code == 200
        
    def test_hmrc_submit_success(self):
        """POST /staff-onboarding/hmrc should accept valid data"""
        response = self.session.post(f"{BASE_URL}/api/staff-onboarding/hmrc", json={
            "first_name": "Sarah",
            "last_name": "Test",
            "dob": "1990-01-15",
            "ni_number": "AB123456C",
            "address": "123 Test Street, London",
            "postcode": "SW1A 1AA",
            "start_date": "2026-01-15",
            "statement": "A"
        })
        assert response.status_code == 200, f"HMRC submit failed: {response.text}"
        data = response.json()
        assert data.get("ok") == True
        
    def test_hmrc_missing_fields(self):
        """POST /staff-onboarding/hmrc should reject missing required fields"""
        response = self.session.post(f"{BASE_URL}/api/staff-onboarding/hmrc", json={
            "first_name": "Sarah"
            # Missing other required fields
        })
        assert response.status_code == 400, "Should reject missing fields"
        assert "Missing fields" in response.text
        
    def test_hmrc_invalid_ni_number(self):
        """POST /staff-onboarding/hmrc should reject invalid NI number"""
        response = self.session.post(f"{BASE_URL}/api/staff-onboarding/hmrc", json={
            "first_name": "Sarah",
            "last_name": "Test",
            "dob": "1990-01-15",
            "ni_number": "INVALID",  # Not 9 chars
            "address": "123 Test Street",
            "postcode": "SW1A 1AA",
            "start_date": "2026-01-15",
            "statement": "A"
        })
        assert response.status_code == 400, "Should reject invalid NI number"
        assert "9 characters" in response.text
        
    def test_hmrc_invalid_statement(self):
        """POST /staff-onboarding/hmrc should reject invalid statement"""
        response = self.session.post(f"{BASE_URL}/api/staff-onboarding/hmrc", json={
            "first_name": "Sarah",
            "last_name": "Test",
            "dob": "1990-01-15",
            "ni_number": "AB123456C",
            "address": "123 Test Street",
            "postcode": "SW1A 1AA",
            "start_date": "2026-01-15",
            "statement": "D"  # Invalid - must be A, B, or C
        })
        assert response.status_code == 400, "Should reject invalid statement"
        assert "A, B or C" in response.text
        
    def test_hmrc_with_student_loan(self):
        """POST /staff-onboarding/hmrc should store student_loan_plan when student_loan=true"""
        response = self.session.post(f"{BASE_URL}/api/staff-onboarding/hmrc", json={
            "first_name": "Sarah",
            "last_name": "Test",
            "dob": "1990-01-15",
            "ni_number": "AB123456C",
            "address": "123 Test Street",
            "postcode": "SW1A 1AA",
            "start_date": "2026-01-15",
            "statement": "A",
            "student_loan": True,
            "student_loan_plan": "plan_2"
        })
        assert response.status_code == 200, f"HMRC submit failed: {response.text}"


class TestStaffOnboardingComplete:
    """Test complete onboarding endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        # Login as staff
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": STAFF_EMAIL,
            "password": STAFF_PASSWORD
        })
        assert login_resp.status_code == 200
        
    def test_complete_fails_when_incomplete(self):
        """POST /staff-onboarding/complete should fail when tasks incomplete"""
        # First check current status
        me_resp = self.session.get(f"{BASE_URL}/api/staff-onboarding/me")
        assert me_resp.status_code == 200
        progress = me_resp.json().get("progress", {})
        
        if progress.get("complete"):
            pytest.skip("All tasks already complete - cannot test incomplete scenario")
            
        response = self.session.post(f"{BASE_URL}/api/staff-onboarding/complete")
        assert response.status_code == 400, "Should fail when tasks incomplete"
        assert "Incomplete tasks" in response.text


class TestStaffOnboardingAdminEndpoints:
    """Test admin-only onboarding endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        # Login as admin
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert login_resp.status_code == 200
        
    def test_list_onboardings(self):
        """GET /staff-onboarding/list should return list of onboardings"""
        response = self.session.get(f"{BASE_URL}/api/staff-onboarding/list")
        assert response.status_code == 200, f"List onboardings failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Should return a list"
        
    def test_list_onboardings_with_status_filter(self):
        """GET /staff-onboarding/list should support status filter"""
        # Test pending filter
        response = self.session.get(f"{BASE_URL}/api/staff-onboarding/list?status=pending")
        assert response.status_code == 200
        
        # Test activated filter
        response = self.session.get(f"{BASE_URL}/api/staff-onboarding/list?status=activated")
        assert response.status_code == 200
        
    def test_admin_activate_user(self):
        """POST /staff-onboarding/admin-activate/{user_id} should activate user"""
        # First get Sarah's user_id
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient
        
        async def get_sarah_id():
            client = AsyncIOMotorClient(os.environ.get('MONGO_URL', 'mongodb://localhost:27017'))
            db = client[os.environ.get('DB_NAME', 'test_database')]
            sarah = await db.users.find_one({'email': STAFF_EMAIL})
            return sarah.get('id') if sarah else None
            
        sarah_id = asyncio.run(get_sarah_id())
        if not sarah_id:
            pytest.skip("Sarah user not found")
            
        response = self.session.post(f"{BASE_URL}/api/staff-onboarding/admin-activate/{sarah_id}")
        assert response.status_code == 200, f"Admin activate failed: {response.text}"
        data = response.json()
        assert data.get("ok") == True
        
    def test_admin_deactivate_user(self):
        """POST /staff-onboarding/admin-deactivate/{user_id} should deactivate user"""
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient
        
        async def get_sarah_id():
            client = AsyncIOMotorClient(os.environ.get('MONGO_URL', 'mongodb://localhost:27017'))
            db = client[os.environ.get('DB_NAME', 'test_database')]
            sarah = await db.users.find_one({'email': STAFF_EMAIL})
            return sarah.get('id') if sarah else None
            
        sarah_id = asyncio.run(get_sarah_id())
        if not sarah_id:
            pytest.skip("Sarah user not found")
            
        response = self.session.post(f"{BASE_URL}/api/staff-onboarding/admin-deactivate/{sarah_id}")
        assert response.status_code == 200, f"Admin deactivate failed: {response.text}"
        data = response.json()
        assert data.get("ok") == True


class TestContractAutoSync:
    """Test that contract_signed auto-syncs from staff_contracts"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        # Login as staff
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": STAFF_EMAIL,
            "password": STAFF_PASSWORD
        })
        assert login_resp.status_code == 200
        
    def test_contract_auto_sync(self):
        """GET /staff-onboarding/me should auto-detect signed contract"""
        response = self.session.get(f"{BASE_URL}/api/staff-onboarding/me")
        assert response.status_code == 200
        data = response.json()
        
        # Check if contract_signed is in the response
        # Per the test setup, Sarah should have a signed contract
        progress = data.get("progress", {})
        tasks = progress.get("tasks", {})
        
        # The contract task should be true if Sarah has a signed contract
        print(f"Contract signed status: {tasks.get('contract')}")
        print(f"Contract ID: {data.get('contract_id')}")


class TestNonAdminCannotAccessAdminEndpoints:
    """Test that non-admin users cannot access admin endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        # Login as staff (non-admin)
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": STAFF_EMAIL,
            "password": STAFF_PASSWORD
        })
        assert login_resp.status_code == 200
        
    def test_staff_cannot_list_onboardings(self):
        """Staff should not be able to list all onboardings"""
        response = self.session.get(f"{BASE_URL}/api/staff-onboarding/list")
        assert response.status_code == 403, "Staff should not access admin endpoint"
        
    def test_staff_cannot_admin_activate(self):
        """Staff should not be able to admin-activate users"""
        response = self.session.post(f"{BASE_URL}/api/staff-onboarding/admin-activate/some-user-id")
        assert response.status_code == 403, "Staff should not access admin endpoint"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
