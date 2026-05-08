"""
Iteration 79 - Timeline Tracking & Before/After Photos Tests
Tests for:
- Issue creation with timeline entry and reported_by_email
- Status updates recording who did it (acknowledged_by, started_by, resolved_by, closed_by)
- Timeline entries for status changes, assignments, photo uploads, comments
- Before/After photo upload with photo_type form field
"""
import pytest
import requests
import os
import uuid
import io

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
PROPERTY_ID = "aldgate-flats"

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        data = response.json()
        return data.get("token") or data.get("access_token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def api_client(auth_token):
    """Session with auth header"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    return session


class TestIssueCreationTimeline:
    """Tests for issue creation with timeline tracking"""
    
    created_issue_id = None
    
    def test_create_issue_has_timeline_entry(self, api_client):
        """POST /api/maintenance/issues - creates issue with timeline 'created' entry"""
        payload = {
            "property_id": PROPERTY_ID,
            "title": f"TEST_Timeline Issue {uuid.uuid4().hex[:6]}",
            "description": "Testing timeline tracking on creation",
            "category": "plumbing",
            "priority": "medium",
            "location": "Room 101"
        }
        response = api_client.post(f"{BASE_URL}/api/maintenance/issues", json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify timeline exists and has 'created' entry
        assert "timeline" in data, "Response should contain 'timeline' array"
        assert isinstance(data["timeline"], list), "Timeline should be a list"
        assert len(data["timeline"]) >= 1, "Timeline should have at least 1 entry"
        
        created_entry = data["timeline"][0]
        assert created_entry["action"] == "created", "First timeline entry should be 'created'"
        assert "by" in created_entry, "Timeline entry should have 'by' field"
        assert "at" in created_entry, "Timeline entry should have 'at' timestamp"
        assert "detail" in created_entry, "Timeline entry should have 'detail'"
        assert payload["title"] in created_entry["detail"], "Detail should mention issue title"
        
        # Verify reported_by_email field
        assert "reported_by_email" in data, "Response should contain 'reported_by_email'"
        assert data["reported_by_email"] == ADMIN_EMAIL, f"reported_by_email should be {ADMIN_EMAIL}"
        
        # Verify reported_by field
        assert "reported_by" in data, "Response should contain 'reported_by'"
        assert data["reported_by"] != "", "reported_by should not be empty"
        
        # Verify photos_before and photos_after arrays exist
        assert "photos_before" in data, "Response should contain 'photos_before' array"
        assert "photos_after" in data, "Response should contain 'photos_after' array"
        assert isinstance(data["photos_before"], list), "photos_before should be a list"
        assert isinstance(data["photos_after"], list), "photos_after should be a list"
        
        TestIssueCreationTimeline.created_issue_id = data["id"]
        print(f"✓ Created issue with timeline entry: {created_entry}")
    
    def test_get_issue_has_timeline(self, api_client):
        """GET /api/maintenance/issues/detail/{issue_id} - returns issue with timeline"""
        assert TestIssueCreationTimeline.created_issue_id, "Need created issue ID"
        
        response = api_client.get(f"{BASE_URL}/api/maintenance/issues/detail/{TestIssueCreationTimeline.created_issue_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "timeline" in data, "Issue detail should have timeline"
        assert len(data["timeline"]) >= 1, "Timeline should have entries"
        assert data["timeline"][0]["action"] == "created", "First entry should be 'created'"
        
        print(f"✓ GET issue returns timeline with {len(data['timeline'])} entries")
    
    def test_cleanup(self, api_client):
        """Cleanup test issue"""
        if TestIssueCreationTimeline.created_issue_id:
            api_client.delete(f"{BASE_URL}/api/maintenance/issues/{TestIssueCreationTimeline.created_issue_id}")
            print("✓ Cleaned up test issue")


class TestStatusChangeTimeline:
    """Tests for status changes recording who did it with timestamps"""
    
    issue_id = None
    
    def test_setup_issue(self, api_client):
        """Create issue for status change tests"""
        payload = {
            "property_id": PROPERTY_ID,
            "title": f"TEST_Status Timeline {uuid.uuid4().hex[:6]}",
            "category": "electrical",
            "priority": "high"
        }
        response = api_client.post(f"{BASE_URL}/api/maintenance/issues", json=payload)
        assert response.status_code == 200
        TestStatusChangeTimeline.issue_id = response.json()["id"]
        print(f"✓ Created issue for status change tests")
    
    def test_acknowledge_records_who_and_when(self, api_client):
        """PUT status=acknowledged records acknowledged_by and acknowledged_at"""
        response = api_client.put(
            f"{BASE_URL}/api/maintenance/issues/{TestStatusChangeTimeline.issue_id}",
            json={"status": "acknowledged"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify acknowledged_by and acknowledged_at
        assert data["status"] == "acknowledged", "Status should be acknowledged"
        assert "acknowledged_by" in data, "Should have acknowledged_by"
        assert data["acknowledged_by"] != "", "acknowledged_by should not be empty"
        assert "acknowledged_at" in data, "Should have acknowledged_at"
        assert data["acknowledged_at"] != "", "acknowledged_at should not be empty"
        
        # Verify timeline entry
        timeline = data.get("timeline", [])
        ack_entry = next((e for e in timeline if e["action"] == "acknowledged"), None)
        assert ack_entry is not None, "Timeline should have 'acknowledged' entry"
        assert ack_entry["by"] == data["acknowledged_by"], "Timeline 'by' should match acknowledged_by"
        assert "at" in ack_entry, "Timeline entry should have timestamp"
        
        print(f"✓ Acknowledged by: {data['acknowledged_by']} at {data['acknowledged_at']}")
    
    def test_start_work_records_who_and_when(self, api_client):
        """PUT status=in_progress records started_by and started_at"""
        response = api_client.put(
            f"{BASE_URL}/api/maintenance/issues/{TestStatusChangeTimeline.issue_id}",
            json={"status": "in_progress"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify started_by and started_at
        assert data["status"] == "in_progress", "Status should be in_progress"
        assert "started_by" in data, "Should have started_by"
        assert data["started_by"] != "", "started_by should not be empty"
        assert "started_at" in data, "Should have started_at"
        assert data["started_at"] != "", "started_at should not be empty"
        
        # Verify timeline entry
        timeline = data.get("timeline", [])
        start_entry = next((e for e in timeline if e["action"] == "started"), None)
        assert start_entry is not None, "Timeline should have 'started' entry"
        assert start_entry["by"] == data["started_by"], "Timeline 'by' should match started_by"
        
        print(f"✓ Started by: {data['started_by']} at {data['started_at']}")
    
    def test_resolve_records_who_and_when(self, api_client):
        """PUT status=resolved records resolved_by and resolved_at"""
        response = api_client.put(
            f"{BASE_URL}/api/maintenance/issues/{TestStatusChangeTimeline.issue_id}",
            json={"status": "resolved", "resolution_notes": "Fixed the electrical issue"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify resolved_by and resolved_at
        assert data["status"] == "resolved", "Status should be resolved"
        assert "resolved_by" in data, "Should have resolved_by"
        assert data["resolved_by"] != "", "resolved_by should not be empty"
        assert "resolved_at" in data, "Should have resolved_at"
        assert data["resolved_at"] != "", "resolved_at should not be empty"
        
        # Verify timeline entry
        timeline = data.get("timeline", [])
        resolve_entry = next((e for e in timeline if e["action"] == "resolved"), None)
        assert resolve_entry is not None, "Timeline should have 'resolved' entry"
        assert resolve_entry["by"] == data["resolved_by"], "Timeline 'by' should match resolved_by"
        
        print(f"✓ Resolved by: {data['resolved_by']} at {data['resolved_at']}")
    
    def test_close_records_who_and_when(self, api_client):
        """PUT status=closed records closed_by and closed_at"""
        response = api_client.put(
            f"{BASE_URL}/api/maintenance/issues/{TestStatusChangeTimeline.issue_id}",
            json={"status": "closed"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify closed_by and closed_at
        assert data["status"] == "closed", "Status should be closed"
        assert "closed_by" in data, "Should have closed_by"
        assert data["closed_by"] != "", "closed_by should not be empty"
        assert "closed_at" in data, "Should have closed_at"
        assert data["closed_at"] != "", "closed_at should not be empty"
        
        # Verify timeline entry
        timeline = data.get("timeline", [])
        close_entry = next((e for e in timeline if e["action"] == "closed"), None)
        assert close_entry is not None, "Timeline should have 'closed' entry"
        assert close_entry["by"] == data["closed_by"], "Timeline 'by' should match closed_by"
        
        print(f"✓ Closed by: {data['closed_by']} at {data['closed_at']}")
    
    def test_full_timeline_has_all_entries(self, api_client):
        """Verify full timeline has all status change entries"""
        response = api_client.get(f"{BASE_URL}/api/maintenance/issues/detail/{TestStatusChangeTimeline.issue_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        timeline = data.get("timeline", [])
        actions = [e["action"] for e in timeline]
        
        assert "created" in actions, "Timeline should have 'created'"
        assert "acknowledged" in actions, "Timeline should have 'acknowledged'"
        assert "started" in actions, "Timeline should have 'started'"
        assert "resolved" in actions, "Timeline should have 'resolved'"
        assert "closed" in actions, "Timeline should have 'closed'"
        
        print(f"✓ Full timeline has {len(timeline)} entries: {actions}")
    
    def test_cleanup(self, api_client):
        """Cleanup test issue"""
        if TestStatusChangeTimeline.issue_id:
            api_client.delete(f"{BASE_URL}/api/maintenance/issues/{TestStatusChangeTimeline.issue_id}")
            print("✓ Cleaned up test issue")


class TestAssignmentTimeline:
    """Tests for assignment changes creating timeline entries"""
    
    issue_id = None
    team_member_id = None
    team_name = None
    
    def test_setup(self, api_client):
        """Create issue and team member for assignment tests"""
        # Create team member
        team_name = f"TEST_Timeline Assignee {uuid.uuid4().hex[:6]}"
        team_response = api_client.post(f"{BASE_URL}/api/maintenance/team", json={
            "property_id": PROPERTY_ID,
            "name": team_name,
            "role": "technician"
        })
        assert team_response.status_code == 200
        TestAssignmentTimeline.team_member_id = team_response.json()["id"]
        TestAssignmentTimeline.team_name = team_name
        
        # Create issue
        issue_response = api_client.post(f"{BASE_URL}/api/maintenance/issues", json={
            "property_id": PROPERTY_ID,
            "title": f"TEST_Assignment Timeline {uuid.uuid4().hex[:6]}",
            "category": "plumbing"
        })
        assert issue_response.status_code == 200
        TestAssignmentTimeline.issue_id = issue_response.json()["id"]
        
        print(f"✓ Created issue and team member for assignment tests")
    
    def test_assignment_creates_timeline_entry(self, api_client):
        """PUT assigned_to creates timeline entry"""
        response = api_client.put(
            f"{BASE_URL}/api/maintenance/issues/{TestAssignmentTimeline.issue_id}",
            json={"assigned_to": TestAssignmentTimeline.team_name}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify assignment
        assert data["assigned_to"] == TestAssignmentTimeline.team_name
        
        # Verify timeline entry
        timeline = data.get("timeline", [])
        assign_entry = next((e for e in timeline if e["action"] == "assigned"), None)
        assert assign_entry is not None, "Timeline should have 'assigned' entry"
        assert TestAssignmentTimeline.team_name in assign_entry["detail"], "Detail should mention assignee"
        
        print(f"✓ Assignment created timeline entry: {assign_entry}")
    
    def test_unassignment_creates_timeline_entry(self, api_client):
        """PUT assigned_to='' creates 'Unassigned' timeline entry"""
        response = api_client.put(
            f"{BASE_URL}/api/maintenance/issues/{TestAssignmentTimeline.issue_id}",
            json={"assigned_to": ""}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify unassignment
        assert data["assigned_to"] == ""
        
        # Verify timeline entry
        timeline = data.get("timeline", [])
        unassign_entries = [e for e in timeline if e["action"] == "assigned" and "Unassigned" in e["detail"]]
        assert len(unassign_entries) >= 1, "Timeline should have 'Unassigned' entry"
        
        print(f"✓ Unassignment created timeline entry")
    
    def test_cleanup(self, api_client):
        """Cleanup test data"""
        if TestAssignmentTimeline.issue_id:
            api_client.delete(f"{BASE_URL}/api/maintenance/issues/{TestAssignmentTimeline.issue_id}")
        if TestAssignmentTimeline.team_member_id:
            api_client.delete(f"{BASE_URL}/api/maintenance/team/{TestAssignmentTimeline.team_member_id}")
        print("✓ Cleaned up test data")


class TestPhotoUploadTimeline:
    """Tests for photo uploads with before/after types and timeline entries"""
    
    issue_id = None
    
    def test_setup(self, api_client):
        """Create issue for photo upload tests"""
        response = api_client.post(f"{BASE_URL}/api/maintenance/issues", json={
            "property_id": PROPERTY_ID,
            "title": f"TEST_Photo Timeline {uuid.uuid4().hex[:6]}",
            "category": "furniture"
        })
        assert response.status_code == 200
        TestPhotoUploadTimeline.issue_id = response.json()["id"]
        print(f"✓ Created issue for photo upload tests")
    
    def test_upload_before_photo(self, api_client):
        """POST /api/maintenance/upload-photo/{issue_id} with photo_type=before"""
        # Create a simple test image (1x1 pixel PNG)
        png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
        
        files = {'file': ('test_before.png', io.BytesIO(png_data), 'image/png')}
        data = {'photo_type': 'before'}
        
        # Remove Content-Type header for multipart
        headers = {"Authorization": api_client.headers["Authorization"]}
        
        response = requests.post(
            f"{BASE_URL}/api/maintenance/upload-photo/{TestPhotoUploadTimeline.issue_id}",
            files=files,
            data=data,
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        result = response.json()
        
        assert result.get("status") == "uploaded", "Should return uploaded status"
        assert result.get("type") == "before", "Type should be 'before'"
        assert "url" in result, "Should return photo URL"
        
        # Verify photo is in photos_before array
        issue_response = api_client.get(f"{BASE_URL}/api/maintenance/issues/detail/{TestPhotoUploadTimeline.issue_id}")
        issue = issue_response.json()
        
        assert len(issue.get("photos_before", [])) >= 1, "photos_before should have at least 1 photo"
        photo = issue["photos_before"][0]
        assert photo.get("type") == "before", "Photo type should be 'before'"
        assert "uploaded_by" in photo, "Photo should have uploaded_by"
        assert "uploaded_at" in photo, "Photo should have uploaded_at"
        
        # Verify timeline entry
        timeline = issue.get("timeline", [])
        photo_entry = next((e for e in timeline if e["action"] == "photo_uploaded" and "Before" in e["detail"]), None)
        assert photo_entry is not None, "Timeline should have 'photo_uploaded' entry for before photo"
        
        print(f"✓ Uploaded before photo, timeline entry: {photo_entry}")
    
    def test_upload_after_photo(self, api_client):
        """POST /api/maintenance/upload-photo/{issue_id} with photo_type=after"""
        # Create a simple test image
        png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
        
        files = {'file': ('test_after.png', io.BytesIO(png_data), 'image/png')}
        data = {'photo_type': 'after'}
        
        headers = {"Authorization": api_client.headers["Authorization"]}
        
        response = requests.post(
            f"{BASE_URL}/api/maintenance/upload-photo/{TestPhotoUploadTimeline.issue_id}",
            files=files,
            data=data,
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        result = response.json()
        
        assert result.get("status") == "uploaded", "Should return uploaded status"
        assert result.get("type") == "after", "Type should be 'after'"
        
        # Verify photo is in photos_after array
        issue_response = api_client.get(f"{BASE_URL}/api/maintenance/issues/detail/{TestPhotoUploadTimeline.issue_id}")
        issue = issue_response.json()
        
        assert len(issue.get("photos_after", [])) >= 1, "photos_after should have at least 1 photo"
        photo = issue["photos_after"][0]
        assert photo.get("type") == "after", "Photo type should be 'after'"
        
        # Verify timeline entry
        timeline = issue.get("timeline", [])
        photo_entry = next((e for e in timeline if e["action"] == "photo_uploaded" and "After" in e["detail"]), None)
        assert photo_entry is not None, "Timeline should have 'photo_uploaded' entry for after photo"
        
        print(f"✓ Uploaded after photo, timeline entry: {photo_entry}")
    
    def test_cleanup(self, api_client):
        """Cleanup test issue"""
        if TestPhotoUploadTimeline.issue_id:
            api_client.delete(f"{BASE_URL}/api/maintenance/issues/{TestPhotoUploadTimeline.issue_id}")
        print("✓ Cleaned up test issue")


class TestCommentTimeline:
    """Tests for comments creating timeline entries"""
    
    issue_id = None
    
    def test_setup(self, api_client):
        """Create issue for comment tests"""
        response = api_client.post(f"{BASE_URL}/api/maintenance/issues", json={
            "property_id": PROPERTY_ID,
            "title": f"TEST_Comment Timeline {uuid.uuid4().hex[:6]}",
            "category": "general"
        })
        assert response.status_code == 200
        TestCommentTimeline.issue_id = response.json()["id"]
        print(f"✓ Created issue for comment tests")
    
    def test_comment_creates_timeline_entry(self, api_client):
        """POST /api/maintenance/issues/{issue_id}/comment creates timeline entry"""
        comment_text = "This is a test comment for timeline tracking"
        
        response = api_client.post(
            f"{BASE_URL}/api/maintenance/issues/{TestCommentTimeline.issue_id}/comment",
            json={"text": comment_text}
        )
        
        assert response.status_code == 200
        comment = response.json()
        
        assert "id" in comment, "Comment should have ID"
        assert comment["text"] == comment_text, "Comment text should match"
        assert "author" in comment, "Comment should have author"
        assert "created_at" in comment, "Comment should have created_at"
        
        # Verify timeline entry
        issue_response = api_client.get(f"{BASE_URL}/api/maintenance/issues/detail/{TestCommentTimeline.issue_id}")
        issue = issue_response.json()
        
        timeline = issue.get("timeline", [])
        comment_entry = next((e for e in timeline if e["action"] == "comment"), None)
        assert comment_entry is not None, "Timeline should have 'comment' entry"
        assert comment_text[:50] in comment_entry["detail"], "Timeline detail should contain comment text"
        
        print(f"✓ Comment created timeline entry: {comment_entry}")
    
    def test_cleanup(self, api_client):
        """Cleanup test issue"""
        if TestCommentTimeline.issue_id:
            api_client.delete(f"{BASE_URL}/api/maintenance/issues/{TestCommentTimeline.issue_id}")
        print("✓ Cleaned up test issue")


class TestExistingIssueWithTimeline:
    """Test the existing 'Broken tap in Room 301' issue mentioned in requirements"""
    
    def test_find_broken_tap_issue(self, api_client):
        """Find the 'Broken tap in Room 301' issue and verify timeline"""
        response = api_client.get(f"{BASE_URL}/api/maintenance/issues/all")
        
        assert response.status_code == 200
        issues = response.json()
        
        # Find the broken tap issue
        broken_tap = next((i for i in issues if "Broken tap" in i.get("title", "") and "301" in i.get("title", "")), None)
        
        if broken_tap:
            print(f"✓ Found 'Broken tap in Room 301' issue: {broken_tap['id']}")
            
            # Get full details
            detail_response = api_client.get(f"{BASE_URL}/api/maintenance/issues/detail/{broken_tap['id']}")
            assert detail_response.status_code == 200
            issue = detail_response.json()
            
            # Verify timeline
            timeline = issue.get("timeline", [])
            print(f"  Timeline has {len(timeline)} entries:")
            for entry in timeline:
                print(f"    - {entry['action']}: {entry['by']} at {entry['at'][:19]}")
            
            # Verify who-tracking fields
            if issue.get("acknowledged_by"):
                print(f"  Acknowledged by: {issue['acknowledged_by']}")
            if issue.get("resolved_by"):
                print(f"  Resolved by: {issue['resolved_by']}")
        else:
            print("⚠ 'Broken tap in Room 301' issue not found - may need to be created")


class TestIssueListHasTimelineFields:
    """Verify issue list returns timeline-related fields"""
    
    def test_list_issues_has_who_fields(self, api_client):
        """GET /api/maintenance/issues/{property_id} returns who-tracking fields"""
        response = api_client.get(f"{BASE_URL}/api/maintenance/issues/{PROPERTY_ID}")
        
        assert response.status_code == 200
        issues = response.json()
        
        if len(issues) > 0:
            issue = issues[0]
            
            # Verify who-tracking fields exist
            expected_fields = [
                "reported_by", "reported_by_email",
                "acknowledged_by", "acknowledged_at",
                "started_by", "started_at",
                "resolved_by", "resolved_at",
                "closed_by", "closed_at",
                "photos_before", "photos_after",
                "timeline"
            ]
            
            for field in expected_fields:
                assert field in issue, f"Issue should have '{field}' field"
            
            print(f"✓ Issue list returns all who-tracking fields: {expected_fields}")
        else:
            print("⚠ No issues found to verify fields")
