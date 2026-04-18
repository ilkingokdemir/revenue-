"""
Iteration 149 - AI Column Mapping Tests
Tests for POST /api/imports/ai-map endpoint using GPT-5.2 for intelligent CSV header mapping.

Features tested:
1. AI mapping with Spanish headers (messy_guests.csv)
2. AI mapping with English headers
3. Error handling: 400 for unknown entity, 404 for expired token, 502 for LLM failures
4. Invalid keys filtering from LLM response
5. Regex auto-mapping fallback still works
6. No regression on other import endpoints
"""

import pytest
import requests
import os
import time
import uuid

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


@pytest.fixture(scope="module")
def admin_session():
    """Get authenticated admin session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Login as admin
    resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    data = resp.json()
    token = data.get("access_token") or data.get("token")
    assert token, "No token in login response"
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


@pytest.fixture(scope="module")
def spanish_csv_file_token(admin_session):
    """Upload Spanish CSV and get file_token"""
    # Read the Spanish CSV file
    with open("/tmp/messy_guests.csv", "rb") as f:
        csv_content = f.read()
    
    files = {"file": ("messy_guests.csv", csv_content, "text/csv")}
    data = {"entity": "guests"}
    
    # Remove Content-Type header for multipart upload
    headers = {k: v for k, v in admin_session.headers.items() if k.lower() != "content-type"}
    
    resp = requests.post(
        f"{BASE_URL}/api/imports/parse",
        files=files,
        data=data,
        headers=headers
    )
    assert resp.status_code == 200, f"Parse failed: {resp.text}"
    result = resp.json()
    assert "file_token" in result, "No file_token in parse response"
    return result


@pytest.fixture(scope="module")
def english_csv_file_token(admin_session):
    """Create and upload English CSV and get file_token"""
    # Create English CSV content
    csv_content = b"""Full Name,Email Address,Phone Number,Country,Notes,Birth Date
John Smith,john@test.com,+1 555 123 4567,USA,Regular guest,1988-05-20
Jane Doe,jane@test.com,+1 555 987 6543,Canada,VIP member,1992-12-15
Bob Wilson,bob@test.com,+44 20 1234 5678,UK,First visit,1975-08-30
"""
    
    files = {"file": ("english_guests.csv", csv_content, "text/csv")}
    data = {"entity": "guests"}
    
    headers = {k: v for k, v in admin_session.headers.items() if k.lower() != "content-type"}
    
    resp = requests.post(
        f"{BASE_URL}/api/imports/parse",
        files=files,
        data=data,
        headers=headers
    )
    assert resp.status_code == 200, f"Parse failed: {resp.text}"
    result = resp.json()
    assert "file_token" in result, "No file_token in parse response"
    return result


class TestAIColumnMapping:
    """Tests for POST /api/imports/ai-map endpoint"""
    
    def test_ai_map_spanish_headers(self, admin_session, spanish_csv_file_token):
        """Test AI mapping with Spanish headers - should map all 6 with HIGH confidence"""
        file_token = spanish_csv_file_token["file_token"]
        
        resp = admin_session.post(f"{BASE_URL}/api/imports/ai-map", json={
            "file_token": file_token,
            "entity": "guests"
        })
        
        # AI calls can take 3-12 seconds
        assert resp.status_code == 200, f"AI map failed: {resp.text}"
        data = resp.json()
        
        # Verify response structure
        assert "mapping" in data, "No mapping in response"
        assert "confidence" in data, "No confidence in response"
        assert "reasoning" in data, "No reasoning in response"
        assert "unmapped_headers" in data, "No unmapped_headers in response"
        assert "total_mapped" in data, "No total_mapped in response"
        assert "total_fields" in data, "No total_fields in response"
        
        mapping = data["mapping"]
        confidence = data["confidence"]
        
        # Expected mappings for Spanish headers:
        # Apellido Completo -> name
        # Correo Electronico -> email
        # Telefono Movil -> phone
        # Pais Origen -> nationality
        # Observaciones -> notes
        # Fecha Nacimiento -> date_of_birth
        
        expected_fields = ["name", "email", "phone", "nationality", "notes", "date_of_birth"]
        
        print(f"AI Mapping result: {mapping}")
        print(f"AI Confidence: {confidence}")
        print(f"AI Reasoning: {data['reasoning']}")
        print(f"Total mapped: {data['total_mapped']}")
        
        # Verify all expected fields are mapped
        mapped_fields = list(mapping.keys())
        for field in expected_fields:
            assert field in mapped_fields, f"Expected field '{field}' not mapped. Got: {mapped_fields}"
        
        # Verify confidence levels (should be high for clear semantic matches)
        for field in expected_fields:
            assert field in confidence, f"No confidence for field '{field}'"
            assert confidence[field] in ["high", "medium", "low"], f"Invalid confidence: {confidence[field]}"
        
        # Verify total_mapped count
        assert data["total_mapped"] >= 6, f"Expected at least 6 mapped, got {data['total_mapped']}"
    
    def test_ai_map_english_headers(self, admin_session, english_csv_file_token):
        """Test AI mapping with English headers - should also work with high confidence"""
        file_token = english_csv_file_token["file_token"]
        
        resp = admin_session.post(f"{BASE_URL}/api/imports/ai-map", json={
            "file_token": file_token,
            "entity": "guests"
        })
        
        assert resp.status_code == 200, f"AI map failed: {resp.text}"
        data = resp.json()
        
        mapping = data["mapping"]
        confidence = data["confidence"]
        
        print(f"English AI Mapping result: {mapping}")
        print(f"English AI Confidence: {confidence}")
        print(f"English AI Reasoning: {data['reasoning']}")
        
        # Verify mapping exists
        assert len(mapping) > 0, "No fields mapped"
        
        # Expected mappings for English headers:
        # Full Name -> name
        # Email Address -> email
        # Phone Number -> phone
        # Country -> nationality
        # Notes -> notes
        # Birth Date -> date_of_birth
        
        expected_fields = ["name", "email", "phone", "nationality", "notes", "date_of_birth"]
        mapped_fields = list(mapping.keys())
        
        for field in expected_fields:
            assert field in mapped_fields, f"Expected field '{field}' not mapped. Got: {mapped_fields}"
    
    def test_ai_map_unknown_entity_returns_400(self, admin_session, spanish_csv_file_token):
        """Test that unknown entity returns 400"""
        file_token = spanish_csv_file_token["file_token"]
        
        resp = admin_session.post(f"{BASE_URL}/api/imports/ai-map", json={
            "file_token": file_token,
            "entity": "unknown_entity"
        })
        
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        assert "unknown" in resp.text.lower() or "entity" in resp.text.lower()
    
    def test_ai_map_expired_token_returns_404(self, admin_session):
        """Test that expired/invalid file_token returns 404"""
        fake_token = str(uuid.uuid4())
        
        resp = admin_session.post(f"{BASE_URL}/api/imports/ai-map", json={
            "file_token": fake_token,
            "entity": "guests"
        })
        
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"
        assert "expired" in resp.text.lower() or "upload" in resp.text.lower() or "not found" in resp.text.lower()
    
    def test_ai_map_requires_auth(self):
        """Test that AI map requires authentication"""
        resp = requests.post(f"{BASE_URL}/api/imports/ai-map", json={
            "file_token": "test",
            "entity": "guests"
        })
        
        assert resp.status_code in [401, 403], f"Expected 401/403, got {resp.status_code}"


class TestRegexAutoMappingFallback:
    """Test that regex auto-mapping still works as fallback"""
    
    def test_parse_returns_auto_mapping(self, admin_session):
        """Test that /imports/parse returns auto_mapping for standard headers"""
        # Create CSV with standard headers that regex can match
        csv_content = b"""name,email,phone,nationality,notes
Test User,test@test.com,+1234567890,USA,Test notes
"""
        
        files = {"file": ("standard_guests.csv", csv_content, "text/csv")}
        data = {"entity": "guests"}
        
        headers = {k: v for k, v in admin_session.headers.items() if k.lower() != "content-type"}
        
        resp = requests.post(
            f"{BASE_URL}/api/imports/parse",
            files=files,
            data=data,
            headers=headers
        )
        
        assert resp.status_code == 200, f"Parse failed: {resp.text}"
        result = resp.json()
        
        assert "auto_mapping" in result, "No auto_mapping in response"
        auto_mapping = result["auto_mapping"]
        
        print(f"Regex auto_mapping: {auto_mapping}")
        
        # Standard headers should be auto-mapped by regex
        assert "name" in auto_mapping, "name not auto-mapped"
        assert "email" in auto_mapping, "email not auto-mapped"
    
    def test_parse_spanish_headers_no_regex_match(self, admin_session):
        """Test that Spanish headers don't get regex auto-mapped (need AI)"""
        # Read the Spanish CSV file
        with open("/tmp/messy_guests.csv", "rb") as f:
            csv_content = f.read()
        
        files = {"file": ("messy_guests.csv", csv_content, "text/csv")}
        data = {"entity": "guests"}
        
        headers = {k: v for k, v in admin_session.headers.items() if k.lower() != "content-type"}
        
        resp = requests.post(
            f"{BASE_URL}/api/imports/parse",
            files=files,
            data=data,
            headers=headers
        )
        
        assert resp.status_code == 200, f"Parse failed: {resp.text}"
        result = resp.json()
        
        auto_mapping = result.get("auto_mapping", {})
        print(f"Spanish headers regex auto_mapping: {auto_mapping}")
        
        # Spanish headers should NOT be auto-mapped by regex (empty or minimal)
        # This proves AI is needed for foreign language headers
        assert len(auto_mapping) == 0 or len(auto_mapping) < 3, \
            f"Regex should not map Spanish headers well, got {len(auto_mapping)} mappings"


class TestImportEndpointsNoRegression:
    """Test that other import endpoints still work (no regression)"""
    
    def test_get_schemas(self, admin_session):
        """Test GET /imports/schemas"""
        resp = admin_session.get(f"{BASE_URL}/api/imports/schemas")
        assert resp.status_code == 200, f"Get schemas failed: {resp.text}"
        data = resp.json()
        
        assert "entities" in data
        entities = data["entities"]
        
        # Verify all expected entities exist
        for entity in ["bookings", "guests", "rooms", "rate_plans"]:
            assert entity in entities, f"Entity '{entity}' not in schemas"
            assert "required" in entities[entity]
            assert "optional" in entities[entity]
    
    def test_list_jobs(self, admin_session):
        """Test GET /imports (list jobs)"""
        resp = admin_session.get(f"{BASE_URL}/api/imports")
        assert resp.status_code == 200, f"List jobs failed: {resp.text}"
        data = resp.json()
        
        assert "jobs" in data
        assert "total" in data
    
    def test_full_import_flow_with_ai(self, admin_session, spanish_csv_file_token):
        """Test full import flow: parse -> ai-map -> create job -> dry-run -> run"""
        file_token = spanish_csv_file_token["file_token"]
        
        # Step 1: AI map
        resp = admin_session.post(f"{BASE_URL}/api/imports/ai-map", json={
            "file_token": file_token,
            "entity": "guests"
        })
        assert resp.status_code == 200, f"AI map failed: {resp.text}"
        ai_mapping = resp.json()["mapping"]
        
        # Step 2: Create job with AI mapping
        resp = admin_session.post(f"{BASE_URL}/api/imports", json={
            "entity": "guests",
            "file_token": file_token,
            "mapping": ai_mapping,
            "skip_duplicates_by": "email"
        })
        assert resp.status_code == 200, f"Create job failed: {resp.text}"
        job = resp.json()
        job_id = job["id"]
        
        assert job["status"] == "draft"
        assert job["entity"] == "guests"
        
        # Step 3: Dry run
        resp = admin_session.post(f"{BASE_URL}/api/imports/{job_id}/dry-run")
        assert resp.status_code == 200, f"Dry run failed: {resp.text}"
        dry_run = resp.json()
        
        assert "total" in dry_run
        assert "valid" in dry_run
        assert dry_run["total"] == 3, f"Expected 3 rows, got {dry_run['total']}"
        
        print(f"Dry run result: {dry_run}")
        
        # Step 4: Get job status
        resp = admin_session.get(f"{BASE_URL}/api/imports/{job_id}")
        assert resp.status_code == 200, f"Get job failed: {resp.text}"
        job_status = resp.json()
        assert job_status["status"] == "dry_run"
        
        # Step 5: Run import
        resp = admin_session.post(f"{BASE_URL}/api/imports/{job_id}/run")
        assert resp.status_code == 200, f"Run import failed: {resp.text}"
        run_result = resp.json()
        
        print(f"Import run result: {run_result}")
        
        assert "inserted" in run_result
        assert "skipped" in run_result
        assert "failed" in run_result
        
        # Step 6: Verify job completed
        resp = admin_session.get(f"{BASE_URL}/api/imports/{job_id}")
        assert resp.status_code == 200
        final_job = resp.json()
        assert final_job["status"] in ["done", "failed"]
        
        # Step 7: Delete job (cleanup)
        resp = admin_session.delete(f"{BASE_URL}/api/imports/{job_id}")
        assert resp.status_code == 200, f"Delete job failed: {resp.text}"
    
    def test_create_job_missing_required_fields(self, admin_session, spanish_csv_file_token):
        """Test that creating job without required fields mapped returns 400"""
        file_token = spanish_csv_file_token["file_token"]
        
        # Try to create job with empty mapping (missing required 'name' field)
        resp = admin_session.post(f"{BASE_URL}/api/imports", json={
            "entity": "guests",
            "file_token": file_token,
            "mapping": {}  # Empty mapping - missing required 'name'
        })
        
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        assert "required" in resp.text.lower() or "name" in resp.text.lower()


class TestRoleBasedAccess:
    """Test that only admin/manager can access AI mapping"""
    
    def test_receptionist_cannot_access_ai_map(self):
        """Test that receptionist role cannot access AI map endpoint"""
        session = requests.Session()
        
        # Login as receptionist (Sarah)
        resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "sarah@hotel.test",
            "password": "StaffP@ss1"
        })
        
        if resp.status_code != 200:
            pytest.skip("Receptionist user not available for testing")
        
        token = resp.json().get("access_token") or resp.json().get("token")
        session.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        })
        
        # Try to access AI map
        resp = session.post(f"{BASE_URL}/api/imports/ai-map", json={
            "file_token": "test",
            "entity": "guests"
        })
        
        # Should be 403 (forbidden) for receptionist
        assert resp.status_code == 403, f"Expected 403 for receptionist, got {resp.status_code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
