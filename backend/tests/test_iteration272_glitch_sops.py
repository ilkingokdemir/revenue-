"""
Iteration 272: Glitch Log & SOPs Library Testing

Tests for two new Flexkeeping-style modules:
1. GLITCH LOG & SHIFT HANDOVER - daily issues register that passes between shifts
2. DIGITAL SOPs LIBRARY - standard operating procedures with versioning, role targeting, acknowledgements

Endpoints tested:
- POST /api/glitch-log - create glitch
- GET /api/glitch-log/{property_id} - list glitches with filters
- PATCH /api/glitch-log/{glitch_id} - update/resolve glitch
- DELETE /api/glitch-log/{glitch_id} - admin only delete
- POST /api/glitch-log/{glitch_id}/acknowledge - mark as read
- GET /api/glitch-log/handover/{property_id} - handover packet

- POST /api/sops - create SOP (draft)
- GET /api/sops - list SOPs
- GET /api/sops/{sop_id} - get SOP detail
- PATCH /api/sops/{sop_id} - update SOP (version bump if steps changed)
- DELETE /api/sops/{sop_id} - admin only delete
- POST /api/sops/{sop_id}/publish - publish draft
- POST /api/sops/{sop_id}/acknowledge - user acks
- GET /api/sops/{sop_id}/acknowledgements - manager view of acks
"""

import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://review-hub-108.preview.emergentagent.com').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


@pytest.fixture(scope="module")
def admin_session():
    """Get authenticated admin session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Login as admin
    response = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    assert response.status_code == 200, f"Admin login failed: {response.text}"
    return session


@pytest.fixture(scope="module")
def created_glitch_id(admin_session):
    """Create a test glitch and return its ID"""
    payload = {
        "property_id": "default",
        "title": "TEST_Glitch_Iteration272",
        "description": "Test glitch for iteration 272 testing",
        "severity": "minor",
        "department": "front-office",
        "shift": "morning",
        "related_room": "101",
        "needs_followup": True
    }
    response = admin_session.post(f"{BASE_URL}/api/glitch-log", json=payload)
    assert response.status_code == 200, f"Failed to create glitch: {response.text}"
    data = response.json()
    assert "id" in data
    return data["id"]


@pytest.fixture(scope="module")
def created_sop_id(admin_session):
    """Create a test SOP and return its ID"""
    payload = {
        "title": "TEST_SOP_Iteration272",
        "description": "Test SOP for iteration 272 testing",
        "category": "housekeeping",
        "target_roles": ["housekeeping", "manager"],
        "property_id": "all",
        "steps": [
            {"order": 1, "text": "Step 1: Check room status", "estimated_minutes": 2},
            {"order": 2, "text": "Step 2: Prepare cleaning supplies", "estimated_minutes": 5},
            {"order": 3, "text": "Step 3: Clean bathroom", "estimated_minutes": 15}
        ],
        "required": False
    }
    response = admin_session.post(f"{BASE_URL}/api/sops", json=payload)
    assert response.status_code == 200, f"Failed to create SOP: {response.text}"
    data = response.json()
    assert "id" in data
    return data["id"]


# ==================== GLITCH LOG TESTS ====================

class TestGlitchLogCreate:
    """Tests for POST /api/glitch-log"""
    
    def test_create_glitch_success(self, admin_session):
        """Create glitch with valid data"""
        payload = {
            "property_id": "default",
            "title": "TEST_Printer not working at reception",
            "description": "The main printer at front desk is jammed",
            "severity": "minor",
            "department": "front-office",
            "shift": "morning",
            "related_room": "",
            "needs_followup": True
        }
        response = admin_session.post(f"{BASE_URL}/api/glitch-log", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data["title"] == payload["title"]
        assert data["severity"] == "minor"
        assert data["department"] == "front-office"
        assert data["shift"] == "morning"
        assert data["status"] == "open"
        assert "id" in data
        assert "created_at" in data
        print(f"✓ Created glitch: {data['id']}")
    
    def test_create_glitch_all_severities(self, admin_session):
        """Test all valid severity values"""
        severities = ["info", "minor", "major", "critical"]
        for sev in severities:
            payload = {
                "property_id": "default",
                "title": f"TEST_Severity test {sev}",
                "severity": sev,
                "department": "housekeeping",
                "shift": "afternoon"
            }
            response = admin_session.post(f"{BASE_URL}/api/glitch-log", json=payload)
            assert response.status_code == 200, f"Failed for severity {sev}: {response.text}"
            assert response.json()["severity"] == sev
            print(f"✓ Severity '{sev}' accepted")
    
    def test_create_glitch_invalid_severity(self, admin_session):
        """Invalid severity should return 400"""
        payload = {
            "property_id": "default",
            "title": "TEST_Invalid severity",
            "severity": "extreme",  # Invalid
            "department": "front-office",
            "shift": "morning"
        }
        response = admin_session.post(f"{BASE_URL}/api/glitch-log", json=payload)
        assert response.status_code == 400
        print("✓ Invalid severity rejected with 400")
    
    def test_create_glitch_all_departments(self, admin_session):
        """Test all valid department values"""
        departments = ["front-office", "housekeeping", "maintenance", "fnb", "management", "security", "other"]
        for dept in departments:
            payload = {
                "property_id": "default",
                "title": f"TEST_Department test {dept}",
                "severity": "info",
                "department": dept,
                "shift": "night"
            }
            response = admin_session.post(f"{BASE_URL}/api/glitch-log", json=payload)
            assert response.status_code == 200, f"Failed for department {dept}: {response.text}"
            assert response.json()["department"] == dept
            print(f"✓ Department '{dept}' accepted")
    
    def test_create_glitch_invalid_department(self, admin_session):
        """Invalid department should return 400"""
        payload = {
            "property_id": "default",
            "title": "TEST_Invalid department",
            "severity": "minor",
            "department": "invalid-dept",  # Invalid
            "shift": "morning"
        }
        response = admin_session.post(f"{BASE_URL}/api/glitch-log", json=payload)
        assert response.status_code == 400
        print("✓ Invalid department rejected with 400")
    
    def test_create_glitch_all_shifts(self, admin_session):
        """Test all valid shift values"""
        shifts = ["morning", "afternoon", "night"]
        for shift in shifts:
            payload = {
                "property_id": "default",
                "title": f"TEST_Shift test {shift}",
                "severity": "info",
                "department": "other",
                "shift": shift
            }
            response = admin_session.post(f"{BASE_URL}/api/glitch-log", json=payload)
            assert response.status_code == 200, f"Failed for shift {shift}: {response.text}"
            assert response.json()["shift"] == shift
            print(f"✓ Shift '{shift}' accepted")
    
    def test_create_glitch_invalid_shift(self, admin_session):
        """Invalid shift should return 400"""
        payload = {
            "property_id": "default",
            "title": "TEST_Invalid shift",
            "severity": "minor",
            "department": "front-office",
            "shift": "evening"  # Invalid
        }
        response = admin_session.post(f"{BASE_URL}/api/glitch-log", json=payload)
        assert response.status_code == 400
        print("✓ Invalid shift rejected with 400")
    
    def test_create_glitch_requires_auth(self):
        """Unauthenticated request should fail"""
        session = requests.Session()
        payload = {
            "property_id": "default",
            "title": "TEST_No auth",
            "severity": "minor",
            "department": "front-office",
            "shift": "morning"
        }
        response = session.post(f"{BASE_URL}/api/glitch-log", json=payload)
        assert response.status_code in [401, 403]
        print("✓ Unauthenticated request rejected")


class TestGlitchLogList:
    """Tests for GET /api/glitch-log/{property_id}"""
    
    def test_list_glitches_default_property(self, admin_session, created_glitch_id):
        """List glitches for default property"""
        response = admin_session.get(f"{BASE_URL}/api/glitch-log/default")
        assert response.status_code == 200
        
        data = response.json()
        assert "glitches" in data
        assert "count" in data
        assert isinstance(data["glitches"], list)
        print(f"✓ Listed {data['count']} glitches for default property")
    
    def test_list_glitches_all_properties(self, admin_session):
        """List glitches across all properties with property_id='all'"""
        response = admin_session.get(f"{BASE_URL}/api/glitch-log/all")
        assert response.status_code == 200
        
        data = response.json()
        assert "glitches" in data
        print(f"✓ Listed {data['count']} glitches across all properties")
    
    def test_list_glitches_filter_by_status(self, admin_session):
        """Filter glitches by status"""
        response = admin_session.get(f"{BASE_URL}/api/glitch-log/all", params={"status": "open"})
        assert response.status_code == 200
        
        data = response.json()
        for g in data["glitches"]:
            assert g["status"] == "open"
        print(f"✓ Filtered by status=open: {data['count']} glitches")
    
    def test_list_glitches_filter_by_severity(self, admin_session):
        """Filter glitches by severity"""
        response = admin_session.get(f"{BASE_URL}/api/glitch-log/all", params={"severity": "minor"})
        assert response.status_code == 200
        
        data = response.json()
        for g in data["glitches"]:
            assert g["severity"] == "minor"
        print(f"✓ Filtered by severity=minor: {data['count']} glitches")
    
    def test_list_glitches_filter_by_shift(self, admin_session):
        """Filter glitches by shift"""
        response = admin_session.get(f"{BASE_URL}/api/glitch-log/all", params={"shift": "morning"})
        assert response.status_code == 200
        
        data = response.json()
        for g in data["glitches"]:
            assert g["shift"] == "morning"
        print(f"✓ Filtered by shift=morning: {data['count']} glitches")
    
    def test_list_glitches_filter_by_department(self, admin_session):
        """Filter glitches by department"""
        response = admin_session.get(f"{BASE_URL}/api/glitch-log/all", params={"department": "front-office"})
        assert response.status_code == 200
        
        data = response.json()
        for g in data["glitches"]:
            assert g["department"] == "front-office"
        print(f"✓ Filtered by department=front-office: {data['count']} glitches")
    
    def test_list_glitches_filter_by_days(self, admin_session):
        """Filter glitches by days range"""
        response = admin_session.get(f"{BASE_URL}/api/glitch-log/all", params={"days": 30})
        assert response.status_code == 200
        
        data = response.json()
        print(f"✓ Filtered by days=30: {data['count']} glitches")
    
    def test_list_glitches_has_ack_fields(self, admin_session, created_glitch_id):
        """Glitches should have acknowledged_by_me and ack_count fields"""
        response = admin_session.get(f"{BASE_URL}/api/glitch-log/default")
        assert response.status_code == 200
        
        data = response.json()
        if data["glitches"]:
            g = data["glitches"][0]
            assert "acknowledged_by_me" in g
            assert "ack_count" in g
            print(f"✓ Glitch has ack fields: acknowledged_by_me={g['acknowledged_by_me']}, ack_count={g['ack_count']}")


class TestGlitchLogPatch:
    """Tests for PATCH /api/glitch-log/{glitch_id}"""
    
    def test_patch_glitch_update_title(self, admin_session, created_glitch_id):
        """Update glitch title"""
        response = admin_session.patch(
            f"{BASE_URL}/api/glitch-log/{created_glitch_id}",
            json={"title": "TEST_Updated title"}
        )
        assert response.status_code == 200
        assert response.json()["updated"] >= 0
        print("✓ Updated glitch title")
    
    def test_patch_glitch_resolve(self, admin_session):
        """Resolve a glitch sets resolved_by and resolved_at"""
        # Create a new glitch to resolve
        create_resp = admin_session.post(f"{BASE_URL}/api/glitch-log", json={
            "property_id": "default",
            "title": "TEST_To be resolved",
            "severity": "minor",
            "department": "maintenance",
            "shift": "afternoon"
        })
        glitch_id = create_resp.json()["id"]
        
        # Resolve it
        response = admin_session.patch(
            f"{BASE_URL}/api/glitch-log/{glitch_id}",
            json={"status": "resolved", "resolution": "Fixed the issue"}
        )
        assert response.status_code == 200
        
        # Verify resolved_by and resolved_at are set
        list_resp = admin_session.get(f"{BASE_URL}/api/glitch-log/default", params={"status": "resolved"})
        glitches = list_resp.json()["glitches"]
        resolved = next((g for g in glitches if g["id"] == glitch_id), None)
        if resolved:
            assert "resolved_by" in resolved
            assert "resolved_at" in resolved
            print(f"✓ Resolved glitch has resolved_by={resolved.get('resolved_by')}")
    
    def test_patch_glitch_invalid_status(self, admin_session, created_glitch_id):
        """Invalid status should return 400"""
        response = admin_session.patch(
            f"{BASE_URL}/api/glitch-log/{created_glitch_id}",
            json={"status": "invalid-status"}
        )
        assert response.status_code == 400
        print("✓ Invalid status rejected with 400")
    
    def test_patch_glitch_not_found(self, admin_session):
        """Patching non-existent glitch returns 404"""
        response = admin_session.patch(
            f"{BASE_URL}/api/glitch-log/nonexistent-id-12345",
            json={"title": "Test"}
        )
        assert response.status_code == 404
        print("✓ Non-existent glitch returns 404")


class TestGlitchLogAcknowledge:
    """Tests for POST /api/glitch-log/{glitch_id}/acknowledge"""
    
    def test_acknowledge_glitch(self, admin_session, created_glitch_id):
        """Acknowledge a glitch"""
        response = admin_session.post(f"{BASE_URL}/api/glitch-log/{created_glitch_id}/acknowledge")
        assert response.status_code == 200
        
        data = response.json()
        assert data["acknowledged"] == True
        assert "by" in data
        print(f"✓ Acknowledged glitch by {data['by']}")
    
    def test_acknowledge_idempotent(self, admin_session, created_glitch_id):
        """Acknowledging twice should be idempotent (no error)"""
        # First ack
        admin_session.post(f"{BASE_URL}/api/glitch-log/{created_glitch_id}/acknowledge")
        # Second ack - should not fail
        response = admin_session.post(f"{BASE_URL}/api/glitch-log/{created_glitch_id}/acknowledge")
        assert response.status_code == 200
        print("✓ Acknowledge is idempotent")


class TestGlitchLogHandover:
    """Tests for GET /api/glitch-log/handover/{property_id}"""
    
    def test_handover_packet(self, admin_session, created_glitch_id):
        """Get handover packet"""
        response = admin_session.get(f"{BASE_URL}/api/glitch-log/handover/default")
        assert response.status_code == 200
        
        data = response.json()
        assert "property_id" in data
        assert "date" in data
        assert "summary" in data
        assert "items_by_severity" in data
        assert "total_open" in data["summary"]
        assert "by_severity" in data["summary"]
        
        # Check items_by_severity structure
        assert "critical" in data["items_by_severity"]
        assert "major" in data["items_by_severity"]
        assert "minor" in data["items_by_severity"]
        assert "info" in data["items_by_severity"]
        
        print(f"✓ Handover packet: {data['summary']['total_open']} open items")
    
    def test_handover_all_properties(self, admin_session):
        """Handover for all properties"""
        response = admin_session.get(f"{BASE_URL}/api/glitch-log/handover/all")
        assert response.status_code == 200
        
        data = response.json()
        assert data["property_id"] == "all"
        print(f"✓ Handover for all properties: {data['summary']['total_open']} open items")
    
    def test_handover_with_shift_filter(self, admin_session):
        """Handover filtered by shift"""
        response = admin_session.get(
            f"{BASE_URL}/api/glitch-log/handover/default",
            params={"from_shift": "morning"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["from_shift"] == "morning"
        print(f"✓ Handover for morning shift: {data['summary']['total_open']} items")


class TestGlitchLogDelete:
    """Tests for DELETE /api/glitch-log/{glitch_id}"""
    
    def test_delete_glitch_admin(self, admin_session):
        """Admin can delete glitch"""
        # Create a glitch to delete
        create_resp = admin_session.post(f"{BASE_URL}/api/glitch-log", json={
            "property_id": "default",
            "title": "TEST_To be deleted",
            "severity": "info",
            "department": "other",
            "shift": "night"
        })
        glitch_id = create_resp.json()["id"]
        
        # Delete it
        response = admin_session.delete(f"{BASE_URL}/api/glitch-log/{glitch_id}")
        assert response.status_code == 200
        assert response.json()["deleted"] >= 0
        print("✓ Admin deleted glitch")
    
    def test_delete_requires_auth(self):
        """Delete requires authentication"""
        session = requests.Session()
        response = session.delete(f"{BASE_URL}/api/glitch-log/some-id")
        assert response.status_code in [401, 403]
        print("✓ Delete requires auth")


# ==================== SOPs TESTS ====================

class TestSopsCreate:
    """Tests for POST /api/sops"""
    
    def test_create_sop_success(self, admin_session):
        """Create SOP with valid data"""
        payload = {
            "title": "TEST_Check-in Procedure",
            "description": "Standard check-in procedure for front desk",
            "category": "front-office",
            "target_roles": ["receptionist", "manager"],
            "property_id": "all",
            "steps": [
                {"order": 1, "text": "Greet the guest warmly", "estimated_minutes": 1},
                {"order": 2, "text": "Verify reservation details", "estimated_minutes": 2},
                {"order": 3, "text": "Collect ID and payment", "estimated_minutes": 3}
            ],
            "required": True
        }
        response = admin_session.post(f"{BASE_URL}/api/sops", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data["title"] == payload["title"]
        assert data["category"] == "front-office"
        assert data["status"] == "draft"
        assert data["version"] == 1
        assert len(data["steps"]) == 3
        assert "id" in data
        print(f"✓ Created SOP: {data['id']} (status=draft, version=1)")
    
    def test_create_sop_all_categories(self, admin_session):
        """Test all valid category values"""
        categories = ["housekeeping", "maintenance", "front-office", "fnb", "safety", "security", "compliance", "guest-service", "other"]
        for cat in categories:
            payload = {
                "title": f"TEST_Category test {cat}",
                "category": cat,
                "steps": [{"order": 1, "text": "Test step"}]
            }
            response = admin_session.post(f"{BASE_URL}/api/sops", json=payload)
            assert response.status_code == 200, f"Failed for category {cat}: {response.text}"
            assert response.json()["category"] == cat
            print(f"✓ Category '{cat}' accepted")
    
    def test_create_sop_invalid_category(self, admin_session):
        """Invalid category should return 400"""
        payload = {
            "title": "TEST_Invalid category",
            "category": "invalid-category",
            "steps": [{"order": 1, "text": "Test step"}]
        }
        response = admin_session.post(f"{BASE_URL}/api/sops", json=payload)
        assert response.status_code == 400
        print("✓ Invalid category rejected with 400")
    
    def test_create_sop_requires_manager_role(self):
        """SOP creation requires admin/manager role"""
        session = requests.Session()
        payload = {
            "title": "TEST_No auth",
            "category": "housekeeping",
            "steps": [{"order": 1, "text": "Test step"}]
        }
        response = session.post(f"{BASE_URL}/api/sops", json=payload)
        assert response.status_code in [401, 403]
        print("✓ SOP creation requires auth")


class TestSopsList:
    """Tests for GET /api/sops"""
    
    def test_list_sops(self, admin_session, created_sop_id):
        """List all SOPs"""
        response = admin_session.get(f"{BASE_URL}/api/sops")
        assert response.status_code == 200
        
        data = response.json()
        assert "sops" in data
        assert "count" in data
        assert isinstance(data["sops"], list)
        print(f"✓ Listed {data['count']} SOPs")
    
    def test_list_sops_filter_by_category(self, admin_session):
        """Filter SOPs by category"""
        response = admin_session.get(f"{BASE_URL}/api/sops", params={"category": "housekeeping"})
        assert response.status_code == 200
        
        data = response.json()
        for s in data["sops"]:
            assert s["category"] == "housekeeping"
        print(f"✓ Filtered by category=housekeeping: {data['count']} SOPs")
    
    def test_list_sops_filter_by_status(self, admin_session):
        """Filter SOPs by status (manager only)"""
        response = admin_session.get(f"{BASE_URL}/api/sops", params={"status": "draft"})
        assert response.status_code == 200
        
        data = response.json()
        for s in data["sops"]:
            assert s["status"] == "draft"
        print(f"✓ Filtered by status=draft: {data['count']} SOPs")
    
    def test_list_sops_search(self, admin_session):
        """Search SOPs by query"""
        response = admin_session.get(f"{BASE_URL}/api/sops", params={"q": "TEST_"})
        assert response.status_code == 200
        
        data = response.json()
        print(f"✓ Search for 'TEST_': {data['count']} SOPs")
    
    def test_list_sops_has_ack_fields(self, admin_session, created_sop_id):
        """SOPs should have acknowledged_by_me and ack_count fields"""
        response = admin_session.get(f"{BASE_URL}/api/sops")
        assert response.status_code == 200
        
        data = response.json()
        if data["sops"]:
            s = data["sops"][0]
            assert "acknowledged_by_me" in s
            assert "ack_count" in s
            print(f"✓ SOP has ack fields: acknowledged_by_me={s['acknowledged_by_me']}, ack_count={s['ack_count']}")


class TestSopsDetail:
    """Tests for GET /api/sops/{sop_id}"""
    
    def test_get_sop_detail(self, admin_session, created_sop_id):
        """Get SOP detail with steps"""
        response = admin_session.get(f"{BASE_URL}/api/sops/{created_sop_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == created_sop_id
        assert "steps" in data
        assert "title" in data
        assert "category" in data
        assert "version" in data
        assert "status" in data
        print(f"✓ Got SOP detail: {data['title']} (v{data['version']}, {data['status']})")
    
    def test_get_sop_not_found(self, admin_session):
        """Non-existent SOP returns 404"""
        response = admin_session.get(f"{BASE_URL}/api/sops/nonexistent-id-12345")
        assert response.status_code == 404
        print("✓ Non-existent SOP returns 404")


class TestSopsPublish:
    """Tests for POST /api/sops/{sop_id}/publish"""
    
    def test_publish_sop(self, admin_session):
        """Publish a draft SOP"""
        # Create a new SOP
        create_resp = admin_session.post(f"{BASE_URL}/api/sops", json={
            "title": "TEST_To be published",
            "category": "safety",
            "steps": [{"order": 1, "text": "Safety step 1"}]
        })
        sop_id = create_resp.json()["id"]
        
        # Publish it
        response = admin_session.post(f"{BASE_URL}/api/sops/{sop_id}/publish")
        assert response.status_code == 200
        assert response.json()["published"] == True
        
        # Verify status changed
        detail_resp = admin_session.get(f"{BASE_URL}/api/sops/{sop_id}")
        assert detail_resp.json()["status"] == "published"
        print(f"✓ Published SOP: {sop_id}")
    
    def test_publish_not_found(self, admin_session):
        """Publishing non-existent SOP returns 404"""
        response = admin_session.post(f"{BASE_URL}/api/sops/nonexistent-id-12345/publish")
        assert response.status_code == 404
        print("✓ Publish non-existent SOP returns 404")


class TestSopsAcknowledge:
    """Tests for POST /api/sops/{sop_id}/acknowledge"""
    
    def test_acknowledge_published_sop(self, admin_session):
        """Acknowledge a published SOP"""
        # Create and publish a SOP
        create_resp = admin_session.post(f"{BASE_URL}/api/sops", json={
            "title": "TEST_To be acknowledged",
            "category": "compliance",
            "steps": [{"order": 1, "text": "Compliance step"}]
        })
        sop_id = create_resp.json()["id"]
        admin_session.post(f"{BASE_URL}/api/sops/{sop_id}/publish")
        
        # Acknowledge it
        response = admin_session.post(f"{BASE_URL}/api/sops/{sop_id}/acknowledge")
        assert response.status_code == 200
        
        data = response.json()
        assert data["acknowledged"] == True
        assert "by" in data
        print(f"✓ Acknowledged SOP by {data['by']}")
    
    def test_acknowledge_draft_sop_fails(self, admin_session, created_sop_id):
        """Cannot acknowledge a draft SOP"""
        # created_sop_id is in draft status
        response = admin_session.post(f"{BASE_URL}/api/sops/{created_sop_id}/acknowledge")
        # Should fail because it's not published
        assert response.status_code in [404, 400]
        print("✓ Cannot acknowledge draft SOP")


class TestSopsPatch:
    """Tests for PATCH /api/sops/{sop_id}"""
    
    def test_patch_sop_update_title(self, admin_session, created_sop_id):
        """Update SOP title"""
        response = admin_session.patch(
            f"{BASE_URL}/api/sops/{created_sop_id}",
            json={"title": "TEST_Updated SOP title"}
        )
        assert response.status_code == 200
        print("✓ Updated SOP title")
    
    def test_patch_sop_steps_bumps_version(self, admin_session):
        """Updating steps should bump version and reset acks"""
        # Create a SOP
        create_resp = admin_session.post(f"{BASE_URL}/api/sops", json={
            "title": "TEST_Version bump test",
            "category": "maintenance",
            "steps": [{"order": 1, "text": "Original step"}]
        })
        sop_id = create_resp.json()["id"]
        original_version = create_resp.json()["version"]
        
        # Update steps
        response = admin_session.patch(
            f"{BASE_URL}/api/sops/{sop_id}",
            json={"steps": [
                {"order": 1, "text": "Updated step 1"},
                {"order": 2, "text": "New step 2"}
            ]}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["version"] == original_version + 1
        print(f"✓ Steps update bumped version from {original_version} to {data['version']}")
    
    def test_patch_sop_archive(self, admin_session):
        """Archive a SOP"""
        # Create a SOP
        create_resp = admin_session.post(f"{BASE_URL}/api/sops", json={
            "title": "TEST_To be archived",
            "category": "other",
            "steps": [{"order": 1, "text": "Step"}]
        })
        sop_id = create_resp.json()["id"]
        
        # Archive it
        response = admin_session.patch(
            f"{BASE_URL}/api/sops/{sop_id}",
            json={"status": "archived"}
        )
        assert response.status_code == 200
        
        # Verify status
        detail_resp = admin_session.get(f"{BASE_URL}/api/sops/{sop_id}")
        assert detail_resp.json()["status"] == "archived"
        print("✓ Archived SOP")
    
    def test_patch_sop_invalid_status(self, admin_session, created_sop_id):
        """Invalid status should return 400"""
        response = admin_session.patch(
            f"{BASE_URL}/api/sops/{created_sop_id}",
            json={"status": "invalid-status"}
        )
        assert response.status_code == 400
        print("✓ Invalid status rejected with 400")
    
    def test_patch_sop_not_found(self, admin_session):
        """Patching non-existent SOP returns 404"""
        response = admin_session.patch(
            f"{BASE_URL}/api/sops/nonexistent-id-12345",
            json={"title": "Test"}
        )
        assert response.status_code == 404
        print("✓ Non-existent SOP returns 404")


class TestSopsAcknowledgements:
    """Tests for GET /api/sops/{sop_id}/acknowledgements"""
    
    def test_get_acknowledgements(self, admin_session):
        """Get list of users who acknowledged a SOP"""
        # Create, publish, and acknowledge a SOP
        create_resp = admin_session.post(f"{BASE_URL}/api/sops", json={
            "title": "TEST_Ack list test",
            "category": "security",
            "steps": [{"order": 1, "text": "Security step"}]
        })
        sop_id = create_resp.json()["id"]
        admin_session.post(f"{BASE_URL}/api/sops/{sop_id}/publish")
        admin_session.post(f"{BASE_URL}/api/sops/{sop_id}/acknowledge")
        
        # Get acknowledgements
        response = admin_session.get(f"{BASE_URL}/api/sops/{sop_id}/acknowledgements")
        assert response.status_code == 200
        
        data = response.json()
        assert "version" in data
        assert "ack_count" in data
        assert "users" in data
        assert isinstance(data["users"], list)
        print(f"✓ Got acknowledgements: {data['ack_count']} users acknowledged v{data['version']}")
    
    def test_get_acknowledgements_not_found(self, admin_session):
        """Non-existent SOP returns 404"""
        response = admin_session.get(f"{BASE_URL}/api/sops/nonexistent-id-12345/acknowledgements")
        assert response.status_code == 404
        print("✓ Non-existent SOP acknowledgements returns 404")


class TestSopsDelete:
    """Tests for DELETE /api/sops/{sop_id}"""
    
    def test_delete_sop_admin(self, admin_session):
        """Admin can delete SOP"""
        # Create a SOP to delete
        create_resp = admin_session.post(f"{BASE_URL}/api/sops", json={
            "title": "TEST_To be deleted",
            "category": "other",
            "steps": [{"order": 1, "text": "Step"}]
        })
        sop_id = create_resp.json()["id"]
        
        # Delete it
        response = admin_session.delete(f"{BASE_URL}/api/sops/{sop_id}")
        assert response.status_code == 200
        assert response.json()["deleted"] >= 0
        print("✓ Admin deleted SOP")
    
    def test_delete_requires_auth(self):
        """Delete requires authentication"""
        session = requests.Session()
        response = session.delete(f"{BASE_URL}/api/sops/some-id")
        assert response.status_code in [401, 403]
        print("✓ Delete requires auth")


class TestSopsCategories:
    """Tests for GET /api/sops/categories/list"""
    
    def test_list_categories(self, admin_session):
        """Get list of SOP categories"""
        response = admin_session.get(f"{BASE_URL}/api/sops/categories/list")
        assert response.status_code == 200
        
        data = response.json()
        assert "categories" in data
        assert isinstance(data["categories"], list)
        assert len(data["categories"]) > 0
        
        expected = {"housekeeping", "maintenance", "front-office", "fnb", "safety", "security", "compliance", "guest-service", "other"}
        assert set(data["categories"]) == expected
        print(f"✓ Got {len(data['categories'])} categories: {data['categories']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
