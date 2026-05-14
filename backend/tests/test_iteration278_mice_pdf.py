"""
Iteration 278 Tests: Meeting & Events Sales (MICE) + Owner Portal PDF Statement

Tests for:
1. Owner Portal PDF Statement download endpoint
2. Full MICE pipeline module with stages, line items, and analytics
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


@pytest.fixture(scope="module")
def auth_token():
    """Get admin auth token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    if response.status_code == 200:
        return response.cookies.get("access_token") or response.json().get("access_token")
    pytest.skip("Authentication failed")


@pytest.fixture(scope="module")
def auth_session(auth_token):
    """Session with auth cookies"""
    session = requests.Session()
    session.cookies.set("access_token", auth_token)
    session.headers.update({"Content-Type": "application/json"})
    return session


# ==================== OWNER PORTAL PDF TESTS ====================

class TestOwnerPortalPDF:
    """Tests for Owner Portal PDF Statement endpoint"""
    
    def test_create_owner_for_pdf_test(self, auth_session):
        """Create an owner to test PDF generation"""
        response = auth_session.post(f"{BASE_URL}/api/owners", json={
            "name": "TEST_PDF_Owner",
            "email": "test_pdf_owner@example.com",
            "phone": "+44123456789",
            "company": "Test Investment Ltd",
            "management_fee_percent": 20.0
        })
        assert response.status_code == 200, f"Failed to create owner: {response.text}"
        data = response.json()
        assert "id" in data
        assert data["name"] == "TEST_PDF_Owner"
        # Store owner_id for subsequent tests
        TestOwnerPortalPDF.owner_id = data["id"]
        print(f"Created owner: {data['id']}")
    
    def test_get_statement_pdf_returns_pdf(self, auth_session):
        """GET /api/owners/{owner_id}/statement.pdf returns application/pdf"""
        owner_id = getattr(TestOwnerPortalPDF, 'owner_id', None)
        if not owner_id:
            pytest.skip("No owner_id from previous test")
        
        month = datetime.now().strftime("%Y-%m")
        response = auth_session.get(f"{BASE_URL}/api/owners/{owner_id}/statement.pdf?month={month}")
        
        assert response.status_code == 200, f"PDF endpoint failed: {response.status_code} - {response.text}"
        
        # Verify content type is PDF
        content_type = response.headers.get("Content-Type", "")
        assert "application/pdf" in content_type, f"Expected PDF content type, got: {content_type}"
        
        # Verify content-disposition header (attachment)
        content_disp = response.headers.get("Content-Disposition", "")
        assert "attachment" in content_disp, f"Expected attachment disposition, got: {content_disp}"
        assert "filename=" in content_disp, "Missing filename in Content-Disposition"
        
        # Verify non-empty body
        assert len(response.content) > 0, "PDF body is empty"
        
        # Verify PDF magic bytes (PDF files start with %PDF)
        assert response.content[:4] == b'%PDF', "Response does not appear to be a valid PDF"
        
        print(f"PDF generated successfully: {len(response.content)} bytes")
    
    def test_statement_pdf_with_invalid_owner_returns_404(self, auth_session):
        """GET /api/owners/{invalid_id}/statement.pdf returns 404"""
        response = auth_session.get(f"{BASE_URL}/api/owners/nonexistent-owner-id/statement.pdf?month=2026-01")
        assert response.status_code == 404


# ==================== MEETINGS SALES (MICE) TESTS ====================

class TestMeetingsSalesList:
    """Tests for GET /api/meetings - list with stage filter"""
    
    def test_list_meetings_empty(self, auth_session):
        """GET /api/meetings returns list structure"""
        response = auth_session.get(f"{BASE_URL}/api/meetings")
        assert response.status_code == 200
        data = response.json()
        assert "meetings" in data
        assert "count" in data
        assert "stages" in data
        assert isinstance(data["meetings"], list)
        print(f"Meetings list: {data['count']} items")
    
    def test_list_meetings_with_stage_filter(self, auth_session):
        """GET /api/meetings?stage=inquiry filters by stage"""
        response = auth_session.get(f"{BASE_URL}/api/meetings?stage=inquiry")
        assert response.status_code == 200
        data = response.json()
        # All returned meetings should have stage=inquiry
        for m in data["meetings"]:
            assert m.get("stage") == "inquiry"


class TestMeetingsSalesCreate:
    """Tests for POST /api/meetings - create RFP"""
    
    def test_create_meeting_rfp(self, auth_session):
        """POST /api/meetings creates RFP with stage='inquiry' and stage_history seeded"""
        response = auth_session.post(f"{BASE_URL}/api/meetings", json={
            "name": "TEST_Corporate Conference 2026",
            "event_type": "corporate_meeting",
            "property_id": "default",
            "contact_name": "John Smith",
            "contact_email": "john@corp.com",
            "contact_phone": "+44987654321",
            "company": "Big Corp Ltd",
            "event_date": "2026-06-15",
            "end_date": "2026-06-17",
            "guests_count": 150,
            "rooms_required": 50,
            "budget_estimate": 25000.0,
            "notes": "Annual corporate retreat",
            "source": "direct"
        })
        assert response.status_code == 200, f"Failed to create meeting: {response.text}"
        data = response.json()
        
        # Verify required fields
        assert "id" in data
        assert data["name"] == "TEST_Corporate Conference 2026"
        assert data["event_type"] == "corporate_meeting"
        
        # Verify stage defaults to 'inquiry'
        assert data["stage"] == "inquiry", f"Expected stage='inquiry', got: {data['stage']}"
        
        # Verify stage_history is seeded
        assert "stage_history" in data
        assert len(data["stage_history"]) >= 1
        assert data["stage_history"][0]["stage"] == "inquiry"
        
        TestMeetingsSalesCreate.meeting_id = data["id"]
        print(f"Created meeting RFP: {data['id']}")
    
    def test_create_meeting_invalid_event_type(self, auth_session):
        """POST /api/meetings with invalid event_type returns 400"""
        response = auth_session.post(f"{BASE_URL}/api/meetings", json={
            "name": "Invalid Event",
            "event_type": "invalid_type",
            "property_id": "default",
            "event_date": "2026-07-01"
        })
        assert response.status_code == 400


class TestMeetingsSalesDetail:
    """Tests for GET /api/meetings/{id} - detail with items and total_estimate"""
    
    def test_get_meeting_detail(self, auth_session):
        """GET /api/meetings/{id} returns detail with items[] and total_estimate"""
        meeting_id = getattr(TestMeetingsSalesCreate, 'meeting_id', None)
        if not meeting_id:
            pytest.skip("No meeting_id from previous test")
        
        response = auth_session.get(f"{BASE_URL}/api/meetings/{meeting_id}")
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == meeting_id
        assert "items" in data, "Missing items[] in detail response"
        assert isinstance(data["items"], list)
        assert "total_estimate" in data, "Missing total_estimate in detail response"
        print(f"Meeting detail: {data['name']}, items: {len(data['items'])}, total: {data['total_estimate']}")
    
    def test_get_meeting_not_found(self, auth_session):
        """GET /api/meetings/{invalid_id} returns 404"""
        response = auth_session.get(f"{BASE_URL}/api/meetings/nonexistent-meeting-id")
        assert response.status_code == 404


class TestMeetingsSalesStageTransition:
    """Tests for PATCH /api/meetings/{id} - stage transitions"""
    
    def test_move_stage_to_confirmed(self, auth_session):
        """PATCH /api/meetings/{id} with {stage:'confirmed'} moves stage and appends to stage_history"""
        meeting_id = getattr(TestMeetingsSalesCreate, 'meeting_id', None)
        if not meeting_id:
            pytest.skip("No meeting_id from previous test")
        
        response = auth_session.patch(f"{BASE_URL}/api/meetings/{meeting_id}", json={
            "stage": "confirmed"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["updated"] == True
        assert "stage" in data["fields"]
        assert "stage_history" in data["fields"]
        
        # Verify stage was updated by fetching detail
        detail = auth_session.get(f"{BASE_URL}/api/meetings/{meeting_id}").json()
        assert detail["stage"] == "confirmed"
        assert len(detail["stage_history"]) >= 2  # inquiry + confirmed
        print(f"Stage moved to confirmed, history: {len(detail['stage_history'])} entries")
    
    def test_move_stage_to_lost_with_reason(self, auth_session):
        """PATCH /api/meetings/{id} with {stage:'lost', lost_reason:'price'} records lost_reason"""
        # Create a new meeting to mark as lost
        create_resp = auth_session.post(f"{BASE_URL}/api/meetings", json={
            "name": "TEST_Lost Deal",
            "event_type": "wedding",
            "property_id": "default",
            "event_date": "2026-08-01"
        })
        assert create_resp.status_code == 200
        lost_meeting_id = create_resp.json()["id"]
        
        # Mark as lost
        response = auth_session.patch(f"{BASE_URL}/api/meetings/{lost_meeting_id}", json={
            "stage": "lost",
            "lost_reason": "price"
        })
        assert response.status_code == 200
        
        # Verify lost_reason is recorded
        detail = auth_session.get(f"{BASE_URL}/api/meetings/{lost_meeting_id}").json()
        assert detail["stage"] == "lost"
        assert detail["lost_reason"] == "price"
        print(f"Meeting marked as lost with reason: {detail['lost_reason']}")
    
    def test_move_stage_invalid_returns_400(self, auth_session):
        """PATCH /api/meetings/{id} with invalid stage returns 400"""
        meeting_id = getattr(TestMeetingsSalesCreate, 'meeting_id', None)
        if not meeting_id:
            pytest.skip("No meeting_id from previous test")
        
        response = auth_session.patch(f"{BASE_URL}/api/meetings/{meeting_id}", json={
            "stage": "invalid_stage"
        })
        assert response.status_code == 400


class TestMeetingsSalesLineItems:
    """Tests for line items: POST /api/meetings/{id}/items and DELETE"""
    
    def test_add_line_item(self, auth_session):
        """POST /api/meetings/{id}/items adds line item with computed subtotal"""
        meeting_id = getattr(TestMeetingsSalesCreate, 'meeting_id', None)
        if not meeting_id:
            pytest.skip("No meeting_id from previous test")
        
        response = auth_session.post(f"{BASE_URL}/api/meetings/{meeting_id}/items", json={
            "kind": "room_block",
            "label": "50 Deluxe Rooms x 2 nights",
            "qty": 100,
            "unit_price": 150.0,
            "notes": "Group rate applied"
        })
        assert response.status_code == 200, f"Failed to add item: {response.text}"
        data = response.json()
        
        assert "id" in data
        assert data["kind"] == "room_block"
        assert data["label"] == "50 Deluxe Rooms x 2 nights"
        assert "subtotal" in data
        assert data["subtotal"] == 100 * 150.0  # qty * unit_price
        
        TestMeetingsSalesLineItems.item_id = data["id"]
        print(f"Added line item: {data['id']}, subtotal: {data['subtotal']}")
    
    def test_add_fnb_item(self, auth_session):
        """POST /api/meetings/{id}/items with kind='fnb' works"""
        meeting_id = getattr(TestMeetingsSalesCreate, 'meeting_id', None)
        if not meeting_id:
            pytest.skip("No meeting_id from previous test")
        
        response = auth_session.post(f"{BASE_URL}/api/meetings/{meeting_id}/items", json={
            "kind": "fnb",
            "label": "Gala Dinner - 150 pax",
            "qty": 150,
            "unit_price": 85.0
        })
        assert response.status_code == 200
        data = response.json()
        assert data["kind"] == "fnb"
        assert data["subtotal"] == 150 * 85.0
    
    def test_add_av_tech_item(self, auth_session):
        """POST /api/meetings/{id}/items with kind='av_tech' works"""
        meeting_id = getattr(TestMeetingsSalesCreate, 'meeting_id', None)
        if not meeting_id:
            pytest.skip("No meeting_id from previous test")
        
        response = auth_session.post(f"{BASE_URL}/api/meetings/{meeting_id}/items", json={
            "kind": "av_tech",
            "label": "Full AV Setup + Technician",
            "qty": 3,
            "unit_price": 500.0
        })
        assert response.status_code == 200
        data = response.json()
        assert data["kind"] == "av_tech"
    
    def test_add_item_invalid_kind_returns_400(self, auth_session):
        """POST /api/meetings/{id}/items with invalid kind returns 400"""
        meeting_id = getattr(TestMeetingsSalesCreate, 'meeting_id', None)
        if not meeting_id:
            pytest.skip("No meeting_id from previous test")
        
        response = auth_session.post(f"{BASE_URL}/api/meetings/{meeting_id}/items", json={
            "kind": "invalid_kind",
            "label": "Test",
            "qty": 1,
            "unit_price": 100.0
        })
        assert response.status_code == 400
    
    def test_delete_line_item(self, auth_session):
        """DELETE /api/meetings/{id}/items/{item_id} removes item"""
        meeting_id = getattr(TestMeetingsSalesCreate, 'meeting_id', None)
        item_id = getattr(TestMeetingsSalesLineItems, 'item_id', None)
        if not meeting_id or not item_id:
            pytest.skip("No meeting_id or item_id from previous tests")
        
        response = auth_session.delete(f"{BASE_URL}/api/meetings/{meeting_id}/items/{item_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] == 1
        print(f"Deleted line item: {item_id}")


class TestMeetingsSalesPipeline:
    """Tests for GET /api/meetings/pipeline - Kanban view"""
    
    def test_get_pipeline(self, auth_session):
        """GET /api/meetings/pipeline returns by_stage grouped + active_value"""
        response = auth_session.get(f"{BASE_URL}/api/meetings/pipeline")
        assert response.status_code == 200
        data = response.json()
        
        assert "by_stage" in data
        assert "active_value" in data
        assert "stages" in data
        
        # Verify by_stage has all expected stages
        expected_stages = ["inquiry", "site_visit", "proposal_sent", "negotiating", 
                          "confirmed", "invoiced", "completed", "lost"]
        for stage in expected_stages:
            assert stage in data["by_stage"], f"Missing stage: {stage}"
        
        # active_value should exclude lost and completed
        print(f"Pipeline active_value: {data['active_value']}")


class TestMeetingsSalesAnalytics:
    """Tests for GET /api/meetings/analytics - conversion funnel"""
    
    def test_get_analytics(self, auth_session):
        """GET /api/meetings/analytics?days=90 returns funnel, win_rate, revenue"""
        response = auth_session.get(f"{BASE_URL}/api/meetings/analytics?days=90")
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields
        assert "period_days" in data
        assert data["period_days"] == 90
        assert "total_inquiries" in data
        assert "funnel" in data
        assert "win_rate_pct" in data
        assert "won_count" in data
        assert "won_revenue_estimate" in data
        assert "avg_deal_size" in data
        assert "lost_count" in data
        assert "lost_reasons" in data
        
        # Verify funnel has all stages
        expected_stages = ["inquiry", "site_visit", "proposal_sent", "negotiating", 
                          "confirmed", "invoiced", "completed", "lost"]
        for stage in expected_stages:
            assert stage in data["funnel"], f"Missing stage in funnel: {stage}"
        
        print(f"Analytics: {data['total_inquiries']} inquiries, win_rate: {data['win_rate_pct']}%")


class TestMeetingsSalesRouteOrdering:
    """Verify /pipeline and /analytics routes work (not matched as meeting_id)"""
    
    def test_pipeline_not_matched_as_meeting_id(self, auth_session):
        """GET /api/meetings/pipeline should NOT return 404 (route ordering correct)"""
        response = auth_session.get(f"{BASE_URL}/api/meetings/pipeline")
        # Should return 200, not 404 (which would happen if 'pipeline' was matched as meeting_id)
        assert response.status_code == 200
        assert "by_stage" in response.json()
    
    def test_analytics_not_matched_as_meeting_id(self, auth_session):
        """GET /api/meetings/analytics should NOT return 404 (route ordering correct)"""
        response = auth_session.get(f"{BASE_URL}/api/meetings/analytics")
        # Should return 200, not 404
        assert response.status_code == 200
        assert "funnel" in response.json()


# ==================== CLEANUP ====================

class TestCleanup:
    """Cleanup test data"""
    
    def test_cleanup_test_meetings(self, auth_session):
        """Remove TEST_ prefixed meetings"""
        response = auth_session.get(f"{BASE_URL}/api/meetings")
        if response.status_code == 200:
            meetings = response.json().get("meetings", [])
            for m in meetings:
                if m.get("name", "").startswith("TEST_"):
                    # Note: No delete endpoint exists, so we just mark as lost
                    auth_session.patch(f"{BASE_URL}/api/meetings/{m['id']}", json={
                        "stage": "lost",
                        "lost_reason": "test_cleanup"
                    })
        print("Test meetings marked as lost for cleanup")
