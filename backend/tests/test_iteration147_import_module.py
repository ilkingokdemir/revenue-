"""
Test Import Module - Iteration 147
Tests for bulk import of bookings, guests, rooms, rate_plans from CSV/XLSX.

Endpoints tested:
- GET /api/imports/schemas - returns 4 entities with required/optional/all_fields
- POST /api/imports/parse - multipart upload, returns file_token, headers, auto_mapping
- POST /api/imports - create job with mapping
- POST /api/imports/{id}/dry-run - validate rows
- POST /api/imports/{id}/run - execute import
- GET /api/imports - list jobs
- GET /api/imports/{id} - get job detail
- DELETE /api/imports/{id} - delete job (admin only)
"""
import pytest
import requests
import os
import io

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

class TestImportModuleSchemas:
    """Test GET /api/imports/schemas endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        # Login as admin
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200, f"Admin login failed: {login_resp.text}"
        self.admin_token = login_resp.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self.admin_token}"})
    
    def test_schemas_returns_4_entities(self):
        """GET /api/imports/schemas returns 4 entities"""
        resp = self.session.get(f"{BASE_URL}/api/imports/schemas")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "entities" in data
        entities = data["entities"]
        assert len(entities) == 4, f"Expected 4 entities, got {len(entities)}"
        assert "bookings" in entities
        assert "guests" in entities
        assert "rooms" in entities
        assert "rate_plans" in entities
    
    def test_schemas_structure(self):
        """Each entity has required, optional, all_fields arrays"""
        resp = self.session.get(f"{BASE_URL}/api/imports/schemas")
        assert resp.status_code == 200
        entities = resp.json()["entities"]
        
        for entity_key, entity in entities.items():
            assert "required" in entity, f"{entity_key} missing required"
            assert "optional" in entity, f"{entity_key} missing optional"
            assert "all_fields" in entity, f"{entity_key} missing all_fields"
            assert isinstance(entity["required"], list)
            assert isinstance(entity["optional"], list)
            assert isinstance(entity["all_fields"], list)
            # all_fields should be required + optional
            assert len(entity["all_fields"]) == len(entity["required"]) + len(entity["optional"])
    
    def test_bookings_schema_fields(self):
        """Bookings entity has correct required fields"""
        resp = self.session.get(f"{BASE_URL}/api/imports/schemas")
        bookings = resp.json()["entities"]["bookings"]
        assert "guest_name" in bookings["required"]
        assert "check_in" in bookings["required"]
        assert "check_out" in bookings["required"]
    
    def test_guests_schema_fields(self):
        """Guests entity has correct required fields"""
        resp = self.session.get(f"{BASE_URL}/api/imports/schemas")
        guests = resp.json()["entities"]["guests"]
        assert "name" in guests["required"]
        assert "email" in guests["optional"]
        assert "phone" in guests["optional"]
    
    def test_rooms_schema_fields(self):
        """Rooms entity has correct required fields"""
        resp = self.session.get(f"{BASE_URL}/api/imports/schemas")
        rooms = resp.json()["entities"]["rooms"]
        assert "room_number" in rooms["required"]
    
    def test_rate_plans_schema_fields(self):
        """Rate plans entity has correct required fields"""
        resp = self.session.get(f"{BASE_URL}/api/imports/schemas")
        rate_plans = resp.json()["entities"]["rate_plans"]
        assert "name" in rate_plans["required"]
        assert "base_rate" in rate_plans["required"]


class TestImportModuleParse:
    """Test POST /api/imports/parse endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        # Login as admin
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200
        self.admin_token = login_resp.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self.admin_token}"})
    
    def test_parse_csv_file(self):
        """POST /api/imports/parse parses CSV and returns expected structure"""
        csv_content = "Name,Email,Phone,Nationality,Notes\nAlice,alice@test.com,+44123,UK,VIP\nBob,bob@test.com,+44456,US,Regular"
        files = {"file": ("test.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        data = {"entity": "guests"}
        
        resp = self.session.post(f"{BASE_URL}/api/imports/parse", files=files, data=data)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        result = resp.json()
        assert "file_token" in result
        assert "filename" in result
        assert "headers" in result
        assert "rows_count" in result
        assert "sample_rows" in result
        assert "auto_mapping" in result
        assert "schema" in result
        
        assert result["rows_count"] == 2
        assert "Name" in result["headers"]
        assert "Email" in result["headers"]
    
    def test_parse_auto_mapping(self):
        """Auto-mapping fuzzy-matches CSV headers to canonical fields"""
        csv_content = "Name,Email,Phone Number,Nationality\nAlice,alice@test.com,+44123,UK"
        files = {"file": ("test.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        data = {"entity": "guests"}
        
        resp = self.session.post(f"{BASE_URL}/api/imports/parse", files=files, data=data)
        assert resp.status_code == 200
        
        auto_mapping = resp.json()["auto_mapping"]
        # "Name" should map to "name"
        assert auto_mapping.get("name") == "Name"
        # "Email" should map to "email"
        assert auto_mapping.get("email") == "Email"
        # "Phone Number" should map to "phone" (fuzzy match)
        assert auto_mapping.get("phone") == "Phone Number"
    
    def test_parse_unknown_entity_400(self):
        """POST /api/imports/parse rejects unknown entity"""
        csv_content = "Name,Email\nAlice,alice@test.com"
        files = {"file": ("test.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        data = {"entity": "unknown_entity"}
        
        resp = self.session.post(f"{BASE_URL}/api/imports/parse", files=files, data=data)
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
    
    def test_parse_unsupported_extension_400(self):
        """POST /api/imports/parse rejects unsupported file extension"""
        files = {"file": ("test.pdf", io.BytesIO(b"fake pdf content"), "application/pdf")}
        data = {"entity": "guests"}
        
        resp = self.session.post(f"{BASE_URL}/api/imports/parse", files=files, data=data)
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
    
    def test_parse_empty_file_400(self):
        """POST /api/imports/parse rejects empty file"""
        files = {"file": ("test.csv", io.BytesIO(b""), "text/csv")}
        data = {"entity": "guests"}
        
        resp = self.session.post(f"{BASE_URL}/api/imports/parse", files=files, data=data)
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
    
    def test_parse_txt_as_csv(self):
        """POST /api/imports/parse accepts .txt files as CSV"""
        csv_content = "Name,Email\nAlice,alice@test.com"
        files = {"file": ("test.txt", io.BytesIO(csv_content.encode()), "text/plain")}
        data = {"entity": "guests"}
        
        resp = self.session.post(f"{BASE_URL}/api/imports/parse", files=files, data=data)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"


class TestImportModuleCreateJob:
    """Test POST /api/imports (create job) endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        # Login as admin
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200
        self.admin_token = login_resp.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self.admin_token}"})
    
    def _upload_csv(self, entity="guests"):
        """Helper to upload a CSV and get file_token"""
        csv_content = "Name,Email,Phone\nTest User,test@test.com,+44123"
        files = {"file": ("test.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        data = {"entity": entity}
        resp = self.session.post(f"{BASE_URL}/api/imports/parse", files=files, data=data)
        assert resp.status_code == 200
        return resp.json()
    
    def test_create_job_success(self):
        """POST /api/imports creates job with status=draft"""
        parsed = self._upload_csv()
        
        job_data = {
            "entity": "guests",
            "file_token": parsed["file_token"],
            "mapping": {"name": "Name", "email": "Email", "phone": "Phone"}
        }
        
        resp = self.session.post(f"{BASE_URL}/api/imports", json=job_data)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        job = resp.json()
        assert "id" in job
        assert job["status"] == "draft"
        assert job["entity"] == "guests"
        assert "created_by_name" in job
    
    def test_create_job_missing_required_mapping_400(self):
        """POST /api/imports rejects when required fields not mapped"""
        parsed = self._upload_csv()
        
        # Missing "name" which is required for guests
        job_data = {
            "entity": "guests",
            "file_token": parsed["file_token"],
            "mapping": {"email": "Email"}  # Missing "name"
        }
        
        resp = self.session.post(f"{BASE_URL}/api/imports", json=job_data)
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        assert "name" in resp.text.lower() or "required" in resp.text.lower()


class TestImportModuleDryRun:
    """Test POST /api/imports/{id}/dry-run endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        # Login as admin
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200
        self.admin_token = login_resp.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self.admin_token}"})
    
    def _create_job(self, csv_content, entity="guests", mapping=None):
        """Helper to upload CSV and create job"""
        files = {"file": ("test.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        data = {"entity": entity}
        parse_resp = self.session.post(f"{BASE_URL}/api/imports/parse", files=files, data=data)
        assert parse_resp.status_code == 200
        parsed = parse_resp.json()
        
        if mapping is None:
            mapping = parsed["auto_mapping"]
        
        job_data = {
            "entity": entity,
            "file_token": parsed["file_token"],
            "mapping": mapping
        }
        job_resp = self.session.post(f"{BASE_URL}/api/imports", json=job_data)
        assert job_resp.status_code == 200
        return job_resp.json()
    
    def test_dry_run_validates_rows(self):
        """POST /api/imports/{id}/dry-run validates rows and returns summary"""
        csv_content = "Name,Email,Phone\nAlice,alice@test.com,+44123\nBob,bob@test.com,+44456"
        job = self._create_job(csv_content)
        
        resp = self.session.post(f"{BASE_URL}/api/imports/{job['id']}/dry-run")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        result = resp.json()
        assert "total" in result
        assert "valid" in result
        assert "errors" in result
        assert "preview" in result
        assert result["total"] == 2
        assert result["valid"] == 2
        assert result["errors"] == 0
    
    def test_dry_run_detects_missing_required(self):
        """Dry-run detects missing required field errors"""
        # Row 2 has empty name (required)
        csv_content = "Name,Email,Phone\nAlice,alice@test.com,+44123\n,bob@test.com,+44456"
        job = self._create_job(csv_content)
        
        resp = self.session.post(f"{BASE_URL}/api/imports/{job['id']}/dry-run")
        assert resp.status_code == 200
        
        result = resp.json()
        assert result["total"] == 2
        assert result["valid"] == 1
        assert result["errors"] == 1
        assert "errors_sample" in result
        assert len(result["errors_sample"]) >= 1
        # Check error mentions missing required field
        error_msg = result["errors_sample"][0]["error"].lower()
        assert "missing" in error_msg or "required" in error_msg
    
    def test_dry_run_detects_invalid_date_format(self):
        """Dry-run detects invalid date format for bookings"""
        csv_content = "guest_name,check_in,check_out\nAlice,2025-01-15,2025-01-20\nBob,invalid-date,2025-01-20"
        job = self._create_job(csv_content, entity="bookings", mapping={
            "guest_name": "guest_name",
            "check_in": "check_in",
            "check_out": "check_out"
        })
        
        resp = self.session.post(f"{BASE_URL}/api/imports/{job['id']}/dry-run")
        assert resp.status_code == 200
        
        result = resp.json()
        assert result["errors"] >= 1
        # Check error mentions invalid date
        error_found = any("date" in e["error"].lower() or "invalid" in e["error"].lower() 
                         for e in result.get("errors_sample", []))
        assert error_found, f"Expected date error, got: {result.get('errors_sample')}"


class TestImportModuleRun:
    """Test POST /api/imports/{id}/run endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        # Login as admin
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200
        self.admin_token = login_resp.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self.admin_token}"})
    
    def _create_and_dryrun_job(self, csv_content, entity="guests", mapping=None, skip_dup_by=None):
        """Helper to upload CSV, create job, and dry-run"""
        files = {"file": ("test.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        data = {"entity": entity}
        parse_resp = self.session.post(f"{BASE_URL}/api/imports/parse", files=files, data=data)
        assert parse_resp.status_code == 200
        parsed = parse_resp.json()
        
        if mapping is None:
            mapping = parsed["auto_mapping"]
        
        job_data = {
            "entity": entity,
            "file_token": parsed["file_token"],
            "mapping": mapping,
            "skip_duplicates_by": skip_dup_by
        }
        job_resp = self.session.post(f"{BASE_URL}/api/imports", json=job_data)
        assert job_resp.status_code == 200
        job = job_resp.json()
        
        # Dry-run
        dry_resp = self.session.post(f"{BASE_URL}/api/imports/{job['id']}/dry-run")
        assert dry_resp.status_code == 200
        
        return job
    
    def test_run_inserts_valid_rows(self):
        """POST /api/imports/{id}/run inserts valid rows"""
        import uuid
        unique_email = f"test_import_{uuid.uuid4().hex[:8]}@test.com"
        csv_content = f"Name,Email,Phone\nImportTest User,{unique_email},+44999"
        job = self._create_and_dryrun_job(csv_content)
        
        resp = self.session.post(f"{BASE_URL}/api/imports/{job['id']}/run")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        result = resp.json()
        assert "inserted" in result
        assert "skipped" in result
        assert "failed" in result
        assert result["inserted"] >= 1
    
    def test_run_skips_duplicates(self):
        """POST /api/imports/{id}/run skips duplicates when skip_duplicates_by is set"""
        import uuid
        unique_email = f"test_dup_{uuid.uuid4().hex[:8]}@test.com"
        
        # First import
        csv_content = f"Name,Email,Phone\nFirst User,{unique_email},+44111"
        job1 = self._create_and_dryrun_job(csv_content, skip_dup_by="email")
        resp1 = self.session.post(f"{BASE_URL}/api/imports/{job1['id']}/run")
        assert resp1.status_code == 200
        assert resp1.json()["inserted"] == 1
        
        # Second import with same email - should skip
        csv_content2 = f"Name,Email,Phone\nDuplicate User,{unique_email},+44222"
        job2 = self._create_and_dryrun_job(csv_content2, skip_dup_by="email")
        resp2 = self.session.post(f"{BASE_URL}/api/imports/{job2['id']}/run")
        assert resp2.status_code == 200
        result2 = resp2.json()
        assert result2["skipped"] == 1, f"Expected 1 skipped, got {result2}"
    
    def test_run_already_completed_400(self):
        """POST /api/imports/{id}/run rejects second run"""
        import uuid
        unique_email = f"test_double_{uuid.uuid4().hex[:8]}@test.com"
        csv_content = f"Name,Email\nDouble Run Test,{unique_email}"
        job = self._create_and_dryrun_job(csv_content)
        
        # First run
        resp1 = self.session.post(f"{BASE_URL}/api/imports/{job['id']}/run")
        assert resp1.status_code == 200
        
        # Second run should fail
        resp2 = self.session.post(f"{BASE_URL}/api/imports/{job['id']}/run")
        assert resp2.status_code == 400, f"Expected 400, got {resp2.status_code}"
        assert "completed" in resp2.text.lower() or "already" in resp2.text.lower()


class TestImportModuleListGetDelete:
    """Test GET /api/imports, GET /api/imports/{id}, DELETE /api/imports/{id}"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        # Login as admin
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200
        self.admin_token = login_resp.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self.admin_token}"})
    
    def test_list_jobs(self):
        """GET /api/imports lists jobs"""
        resp = self.session.get(f"{BASE_URL}/api/imports")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "jobs" in data
        assert "total" in data
        assert isinstance(data["jobs"], list)
    
    def test_get_job_detail(self):
        """GET /api/imports/{id} returns job detail with errors"""
        # Create a job first
        csv_content = "Name,Email\nTest,test@test.com"
        files = {"file": ("test.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        data = {"entity": "guests"}
        parse_resp = self.session.post(f"{BASE_URL}/api/imports/parse", files=files, data=data)
        parsed = parse_resp.json()
        
        job_data = {
            "entity": "guests",
            "file_token": parsed["file_token"],
            "mapping": {"name": "Name", "email": "Email"}
        }
        job_resp = self.session.post(f"{BASE_URL}/api/imports", json=job_data)
        job = job_resp.json()
        
        # Get job detail
        resp = self.session.get(f"{BASE_URL}/api/imports/{job['id']}")
        assert resp.status_code == 200
        
        detail = resp.json()
        assert detail["id"] == job["id"]
        assert "entity" in detail
        assert "status" in detail
        assert "mapping" in detail
    
    def test_delete_job_admin_only(self):
        """DELETE /api/imports/{id} requires admin role"""
        # Create a job as admin
        csv_content = "Name,Email\nDeleteTest,delete@test.com"
        files = {"file": ("test.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        data = {"entity": "guests"}
        parse_resp = self.session.post(f"{BASE_URL}/api/imports/parse", files=files, data=data)
        parsed = parse_resp.json()
        
        job_data = {
            "entity": "guests",
            "file_token": parsed["file_token"],
            "mapping": {"name": "Name", "email": "Email"}
        }
        job_resp = self.session.post(f"{BASE_URL}/api/imports", json=job_data)
        job = job_resp.json()
        
        # Delete as admin should work
        resp = self.session.delete(f"{BASE_URL}/api/imports/{job['id']}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        # Verify deleted
        get_resp = self.session.get(f"{BASE_URL}/api/imports/{job['id']}")
        assert get_resp.status_code == 404


class TestImportModuleRoleAccess:
    """Test role-based access control for import endpoints"""
    
    def test_receptionist_cannot_access_parse(self):
        """Receptionist cannot access POST /api/imports/parse"""
        session = requests.Session()
        # Login as receptionist
        login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "sarah@hotel.test",
            "password": "StaffP@ss1"
        })
        if login_resp.status_code != 200:
            pytest.skip("Receptionist user not available")
        
        token = login_resp.json().get("access_token")
        session.headers.update({"Authorization": f"Bearer {token}"})
        
        csv_content = "Name,Email\nTest,test@test.com"
        files = {"file": ("test.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        data = {"entity": "guests"}
        
        resp = session.post(f"{BASE_URL}/api/imports/parse", files=files, data=data)
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"
    
    def test_receptionist_cannot_delete_job(self):
        """Receptionist cannot delete import jobs"""
        # First create a job as admin
        admin_session = requests.Session()
        login_resp = admin_session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        admin_token = login_resp.json().get("access_token")
        admin_session.headers.update({"Authorization": f"Bearer {admin_token}"})
        
        csv_content = "Name,Email\nRoleTest,role@test.com"
        files = {"file": ("test.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        data = {"entity": "guests"}
        parse_resp = admin_session.post(f"{BASE_URL}/api/imports/parse", files=files, data=data)
        parsed = parse_resp.json()
        
        job_data = {
            "entity": "guests",
            "file_token": parsed["file_token"],
            "mapping": {"name": "Name", "email": "Email"}
        }
        job_resp = admin_session.post(f"{BASE_URL}/api/imports", json=job_data)
        job = job_resp.json()
        
        # Try to delete as receptionist
        recep_session = requests.Session()
        login_resp = recep_session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "sarah@hotel.test",
            "password": "StaffP@ss1"
        })
        if login_resp.status_code != 200:
            # Clean up and skip
            admin_session.delete(f"{BASE_URL}/api/imports/{job['id']}")
            pytest.skip("Receptionist user not available")
        
        recep_token = login_resp.json().get("access_token")
        recep_session.headers.update({"Authorization": f"Bearer {recep_token}"})
        
        resp = recep_session.delete(f"{BASE_URL}/api/imports/{job['id']}")
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"
        
        # Clean up
        admin_session.delete(f"{BASE_URL}/api/imports/{job['id']}")


class TestImportModuleWithTestFile:
    """Test using the provided /tmp/test_guests.csv file"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        # Login as admin
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200
        self.admin_token = login_resp.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self.admin_token}"})
    
    def test_parse_test_guests_csv(self):
        """Parse the test_guests.csv file"""
        # Read the test file
        with open("/tmp/test_guests.csv", "rb") as f:
            file_content = f.read()
        
        files = {"file": ("test_guests.csv", io.BytesIO(file_content), "text/csv")}
        data = {"entity": "guests"}
        
        resp = self.session.post(f"{BASE_URL}/api/imports/parse", files=files, data=data)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        result = resp.json()
        assert result["rows_count"] == 5, f"Expected 5 rows, got {result['rows_count']}"
        
        # Check auto-mapping
        auto_mapping = result["auto_mapping"]
        assert auto_mapping.get("name") == "Name"
        assert auto_mapping.get("email") == "Email"
        assert auto_mapping.get("phone") == "Phone"
        assert auto_mapping.get("nationality") == "Nationality"
    
    def test_full_import_flow_with_test_file(self):
        """Full import flow: parse -> create job -> dry-run -> run"""
        import uuid
        
        # Create unique test data to avoid conflicts
        unique_suffix = uuid.uuid4().hex[:6]
        csv_content = f"""Name,Email,Phone,Nationality,Notes
TestAlice_{unique_suffix},alice_{unique_suffix}@test.com,+44 7700 900123,UK,VIP corporate
TestBob_{unique_suffix},bob_{unique_suffix}@test.com,+44 7700 900456,China,Allergic to nuts
TestCarla_{unique_suffix},carla_{unique_suffix}@test.com,+44 7700 900789,Spain,Regular guest
TestDup_{unique_suffix},alice_{unique_suffix}@test.com,+44 7700 900000,UK,Should be skipped if dedupe
,nomail_{unique_suffix}@test.com,+44 7700 900999,Germany,Missing name - should fail"""
        
        # Step 1: Parse
        files = {"file": ("test.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        data = {"entity": "guests"}
        parse_resp = self.session.post(f"{BASE_URL}/api/imports/parse", files=files, data=data)
        assert parse_resp.status_code == 200
        parsed = parse_resp.json()
        assert parsed["rows_count"] == 5
        
        # Step 2: Create job with skip_duplicates_by=email
        job_data = {
            "entity": "guests",
            "file_token": parsed["file_token"],
            "mapping": parsed["auto_mapping"],
            "skip_duplicates_by": "email"
        }
        job_resp = self.session.post(f"{BASE_URL}/api/imports", json=job_data)
        assert job_resp.status_code == 200
        job = job_resp.json()
        assert job["status"] == "draft"
        
        # Step 3: Dry-run
        dry_resp = self.session.post(f"{BASE_URL}/api/imports/{job['id']}/dry-run")
        assert dry_resp.status_code == 200
        dry_result = dry_resp.json()
        assert dry_result["total"] == 5
        assert dry_result["valid"] == 4  # 1 row missing name
        assert dry_result["errors"] == 1
        
        # Step 4: Run
        run_resp = self.session.post(f"{BASE_URL}/api/imports/{job['id']}/run")
        assert run_resp.status_code == 200
        run_result = run_resp.json()
        
        # Expected: 3 inserted (Alice, Bob, Carla), 1 skipped (Dup has same email as Alice), 1 failed (missing name)
        assert run_result["inserted"] == 3, f"Expected 3 inserted, got {run_result}"
        assert run_result["skipped"] == 1, f"Expected 1 skipped, got {run_result}"
        assert run_result["failed"] == 1, f"Expected 1 failed, got {run_result}"
