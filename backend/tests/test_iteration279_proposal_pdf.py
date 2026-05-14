"""
Iteration 279 Tests: Meeting Proposal PDF with Auto-Stage Advance

Tests for:
1. GET /api/meetings/{id}/proposal.pdf - returns application/pdf with non-empty body (>2KB, starts with %PDF-)
2. PDF download auto-advances stage from 'inquiry' to 'proposal_sent'
3. PDF download auto-advances stage from 'site_visit' to 'proposal_sent'
4. PDF download does NOT advance stage if already past proposal_sent (e.g., confirmed stays confirmed)
5. GET /api/meetings/{id}/proposal.pdf on non-existent id returns 404
6. Regression: All 22 tests from iteration 278 still pass
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


# ==================== PROPOSAL PDF TESTS ====================

class TestProposalPDFBasic:
    """Tests for GET /api/meetings/{id}/proposal.pdf - basic PDF generation"""
    
    def test_create_meeting_for_pdf_test(self, auth_session):
        """Create a meeting with items to test PDF generation"""
        # Create meeting
        response = auth_session.post(f"{BASE_URL}/api/meetings", json={
            "name": "TEST_PDF_Wedding_2026",
            "event_type": "wedding",
            "property_id": "default",
            "contact_name": "Jane Doe",
            "contact_email": "jane@wedding.com",
            "contact_phone": "+44111222333",
            "company": "Wedding Planners Ltd",
            "event_date": "2026-09-15",
            "end_date": "2026-09-16",
            "guests_count": 200,
            "rooms_required": 80,
            "budget_estimate": 50000.0,
            "notes": "Luxury wedding reception"
        })
        assert response.status_code == 200, f"Failed to create meeting: {response.text}"
        data = response.json()
        TestProposalPDFBasic.meeting_id = data["id"]
        
        # Add line items for PDF content
        items = [
            {"kind": "room_block", "label": "80 Deluxe Rooms x 2 nights", "qty": 160, "unit_price": 180.0},
            {"kind": "fnb", "label": "Wedding Dinner - 200 pax", "qty": 200, "unit_price": 95.0},
            {"kind": "fnb", "label": "Cocktail Reception", "qty": 200, "unit_price": 35.0},
            {"kind": "meeting_space", "label": "Grand Ballroom Full Day", "qty": 2, "unit_price": 2500.0},
            {"kind": "av_tech", "label": "DJ + Sound System", "qty": 1, "unit_price": 1500.0},
            {"kind": "decor", "label": "Floral Arrangements", "qty": 1, "unit_price": 3000.0},
        ]
        for item in items:
            item_resp = auth_session.post(f"{BASE_URL}/api/meetings/{data['id']}/items", json=item)
            assert item_resp.status_code == 200, f"Failed to add item: {item_resp.text}"
        
        print(f"Created meeting with {len(items)} items: {data['id']}")
    
    def test_proposal_pdf_returns_valid_pdf(self, auth_session):
        """GET /api/meetings/{id}/proposal.pdf returns application/pdf with non-empty body (>2KB, starts with %PDF-)"""
        meeting_id = getattr(TestProposalPDFBasic, 'meeting_id', None)
        if not meeting_id:
            pytest.skip("No meeting_id from previous test")
        
        response = auth_session.get(f"{BASE_URL}/api/meetings/{meeting_id}/proposal.pdf")
        
        assert response.status_code == 200, f"PDF endpoint failed: {response.status_code} - {response.text}"
        
        # Verify content type is PDF
        content_type = response.headers.get("Content-Type", "")
        assert "application/pdf" in content_type, f"Expected PDF content type, got: {content_type}"
        
        # Verify content-disposition header (attachment)
        content_disp = response.headers.get("Content-Disposition", "")
        assert "attachment" in content_disp, f"Expected attachment disposition, got: {content_disp}"
        assert "filename=" in content_disp, "Missing filename in Content-Disposition"
        
        # Verify non-empty body (>2KB for a proper PDF with content)
        pdf_size = len(response.content)
        assert pdf_size > 2000, f"PDF body too small: {pdf_size} bytes (expected >2KB)"
        
        # Verify PDF magic bytes (PDF files start with %PDF)
        assert response.content[:4] == b'%PDF', "Response does not appear to be a valid PDF"
        
        print(f"PDF generated successfully: {pdf_size} bytes")
    
    def test_proposal_pdf_nonexistent_meeting_returns_404(self, auth_session):
        """GET /api/meetings/{id}/proposal.pdf on non-existent id returns 404"""
        response = auth_session.get(f"{BASE_URL}/api/meetings/nonexistent-meeting-id-12345/proposal.pdf")
        assert response.status_code == 404, f"Expected 404, got: {response.status_code}"


class TestProposalPDFAutoAdvanceFromInquiry:
    """Tests for PDF download auto-advancing stage from 'inquiry' to 'proposal_sent'"""
    
    def test_create_inquiry_meeting(self, auth_session):
        """Create a meeting in 'inquiry' stage"""
        response = auth_session.post(f"{BASE_URL}/api/meetings", json={
            "name": "TEST_Inquiry_AutoAdvance",
            "event_type": "corporate_meeting",
            "property_id": "default",
            "contact_name": "Bob Corp",
            "contact_email": "bob@corp.com",
            "event_date": "2026-10-01",
            "guests_count": 50
        })
        assert response.status_code == 200
        data = response.json()
        assert data["stage"] == "inquiry", f"Expected stage='inquiry', got: {data['stage']}"
        TestProposalPDFAutoAdvanceFromInquiry.meeting_id = data["id"]
        TestProposalPDFAutoAdvanceFromInquiry.initial_history_len = len(data.get("stage_history", []))
        
        # Add at least one item for PDF
        auth_session.post(f"{BASE_URL}/api/meetings/{data['id']}/items", json={
            "kind": "meeting_space", "label": "Conference Room", "qty": 1, "unit_price": 500.0
        })
        print(f"Created inquiry meeting: {data['id']}")
    
    def test_pdf_download_advances_inquiry_to_proposal_sent(self, auth_session):
        """PDF download auto-advances stage from 'inquiry' to 'proposal_sent' and stamps proposal_sent_at"""
        meeting_id = getattr(TestProposalPDFAutoAdvanceFromInquiry, 'meeting_id', None)
        initial_history_len = getattr(TestProposalPDFAutoAdvanceFromInquiry, 'initial_history_len', 0)
        if not meeting_id:
            pytest.skip("No meeting_id from previous test")
        
        # Download PDF
        response = auth_session.get(f"{BASE_URL}/api/meetings/{meeting_id}/proposal.pdf")
        assert response.status_code == 200
        
        # Verify stage was advanced
        detail = auth_session.get(f"{BASE_URL}/api/meetings/{meeting_id}").json()
        assert detail["stage"] == "proposal_sent", f"Expected stage='proposal_sent', got: {detail['stage']}"
        
        # Verify stage_history gained one entry
        new_history_len = len(detail.get("stage_history", []))
        assert new_history_len == initial_history_len + 1, \
            f"Expected stage_history to gain 1 entry (was {initial_history_len}, now {new_history_len})"
        
        # Verify last history entry is 'proposal_sent'
        last_entry = detail["stage_history"][-1]
        assert last_entry["stage"] == "proposal_sent"
        
        # Verify proposal_sent_at is set
        assert "proposal_sent_at" in detail, "Missing proposal_sent_at timestamp"
        assert detail["proposal_sent_at"] is not None
        
        print(f"Stage auto-advanced from inquiry to proposal_sent, proposal_sent_at: {detail['proposal_sent_at']}")


class TestProposalPDFAutoAdvanceFromSiteVisit:
    """Tests for PDF download auto-advancing stage from 'site_visit' to 'proposal_sent'"""
    
    def test_create_site_visit_meeting(self, auth_session):
        """Create a meeting and move to 'site_visit' stage"""
        # Create meeting
        response = auth_session.post(f"{BASE_URL}/api/meetings", json={
            "name": "TEST_SiteVisit_AutoAdvance",
            "event_type": "conference",
            "property_id": "default",
            "contact_name": "Alice Conf",
            "contact_email": "alice@conf.com",
            "event_date": "2026-11-15",
            "guests_count": 300
        })
        assert response.status_code == 200
        data = response.json()
        meeting_id = data["id"]
        
        # Move to site_visit stage
        patch_resp = auth_session.patch(f"{BASE_URL}/api/meetings/{meeting_id}", json={
            "stage": "site_visit"
        })
        assert patch_resp.status_code == 200
        
        # Verify stage is site_visit
        detail = auth_session.get(f"{BASE_URL}/api/meetings/{meeting_id}").json()
        assert detail["stage"] == "site_visit"
        
        TestProposalPDFAutoAdvanceFromSiteVisit.meeting_id = meeting_id
        TestProposalPDFAutoAdvanceFromSiteVisit.initial_history_len = len(detail.get("stage_history", []))
        
        # Add item for PDF
        auth_session.post(f"{BASE_URL}/api/meetings/{meeting_id}/items", json={
            "kind": "fnb", "label": "Conference Lunch", "qty": 300, "unit_price": 45.0
        })
        print(f"Created site_visit meeting: {meeting_id}")
    
    def test_pdf_download_advances_site_visit_to_proposal_sent(self, auth_session):
        """PDF download auto-advances stage from 'site_visit' to 'proposal_sent'"""
        meeting_id = getattr(TestProposalPDFAutoAdvanceFromSiteVisit, 'meeting_id', None)
        initial_history_len = getattr(TestProposalPDFAutoAdvanceFromSiteVisit, 'initial_history_len', 0)
        if not meeting_id:
            pytest.skip("No meeting_id from previous test")
        
        # Download PDF
        response = auth_session.get(f"{BASE_URL}/api/meetings/{meeting_id}/proposal.pdf")
        assert response.status_code == 200
        
        # Verify stage was advanced
        detail = auth_session.get(f"{BASE_URL}/api/meetings/{meeting_id}").json()
        assert detail["stage"] == "proposal_sent", f"Expected stage='proposal_sent', got: {detail['stage']}"
        
        # Verify stage_history gained one entry
        new_history_len = len(detail.get("stage_history", []))
        assert new_history_len == initial_history_len + 1
        
        # Verify proposal_sent_at is set
        assert detail.get("proposal_sent_at") is not None
        
        print(f"Stage auto-advanced from site_visit to proposal_sent")


class TestProposalPDFNoAdvanceIfPastProposalSent:
    """Tests that PDF download does NOT advance stage if already past proposal_sent"""
    
    def test_create_confirmed_meeting(self, auth_session):
        """Create a meeting and move to 'confirmed' stage (past proposal_sent)"""
        # Create meeting
        response = auth_session.post(f"{BASE_URL}/api/meetings", json={
            "name": "TEST_Confirmed_NoAdvance",
            "event_type": "gala",
            "property_id": "default",
            "contact_name": "Charlie Gala",
            "contact_email": "charlie@gala.com",
            "event_date": "2026-12-20",
            "guests_count": 500
        })
        assert response.status_code == 200
        data = response.json()
        meeting_id = data["id"]
        
        # Move to confirmed stage (past proposal_sent)
        patch_resp = auth_session.patch(f"{BASE_URL}/api/meetings/{meeting_id}", json={
            "stage": "confirmed"
        })
        assert patch_resp.status_code == 200
        
        # Verify stage is confirmed
        detail = auth_session.get(f"{BASE_URL}/api/meetings/{meeting_id}").json()
        assert detail["stage"] == "confirmed"
        
        TestProposalPDFNoAdvanceIfPastProposalSent.meeting_id = meeting_id
        TestProposalPDFNoAdvanceIfPastProposalSent.initial_history_len = len(detail.get("stage_history", []))
        
        # Add item for PDF
        auth_session.post(f"{BASE_URL}/api/meetings/{meeting_id}/items", json={
            "kind": "decor", "label": "Gala Decorations", "qty": 1, "unit_price": 10000.0
        })
        print(f"Created confirmed meeting: {meeting_id}")
    
    def test_pdf_download_does_not_advance_confirmed_stage(self, auth_session):
        """PDF download does NOT advance stage if already 'confirmed' (past proposal_sent)"""
        meeting_id = getattr(TestProposalPDFNoAdvanceIfPastProposalSent, 'meeting_id', None)
        initial_history_len = getattr(TestProposalPDFNoAdvanceIfPastProposalSent, 'initial_history_len', 0)
        if not meeting_id:
            pytest.skip("No meeting_id from previous test")
        
        # Download PDF
        response = auth_session.get(f"{BASE_URL}/api/meetings/{meeting_id}/proposal.pdf")
        assert response.status_code == 200
        
        # Verify stage was NOT changed
        detail = auth_session.get(f"{BASE_URL}/api/meetings/{meeting_id}").json()
        assert detail["stage"] == "confirmed", f"Stage should remain 'confirmed', got: {detail['stage']}"
        
        # Verify stage_history did NOT gain an entry
        new_history_len = len(detail.get("stage_history", []))
        assert new_history_len == initial_history_len, \
            f"stage_history should not change (was {initial_history_len}, now {new_history_len})"
        
        print(f"Stage correctly remained 'confirmed' after PDF download")
    
    def test_pdf_download_does_not_advance_invoiced_stage(self, auth_session):
        """PDF download does NOT advance stage if already 'invoiced'"""
        # Create and move to invoiced
        response = auth_session.post(f"{BASE_URL}/api/meetings", json={
            "name": "TEST_Invoiced_NoAdvance",
            "event_type": "training",
            "property_id": "default",
            "event_date": "2027-01-10",
            "guests_count": 30
        })
        assert response.status_code == 200
        meeting_id = response.json()["id"]
        
        # Move to invoiced
        auth_session.patch(f"{BASE_URL}/api/meetings/{meeting_id}", json={"stage": "invoiced"})
        
        # Add item
        auth_session.post(f"{BASE_URL}/api/meetings/{meeting_id}/items", json={
            "kind": "meeting_space", "label": "Training Room", "qty": 1, "unit_price": 300.0
        })
        
        # Get initial state
        detail_before = auth_session.get(f"{BASE_URL}/api/meetings/{meeting_id}").json()
        history_len_before = len(detail_before.get("stage_history", []))
        
        # Download PDF
        pdf_resp = auth_session.get(f"{BASE_URL}/api/meetings/{meeting_id}/proposal.pdf")
        assert pdf_resp.status_code == 200
        
        # Verify stage unchanged
        detail_after = auth_session.get(f"{BASE_URL}/api/meetings/{meeting_id}").json()
        assert detail_after["stage"] == "invoiced"
        assert len(detail_after.get("stage_history", [])) == history_len_before
        
        print("Stage correctly remained 'invoiced' after PDF download")


class TestProposalPDFRouteOrdering:
    """Verify /{meeting_id}/proposal.pdf route works correctly (not conflicting with other routes)"""
    
    def test_proposal_pdf_route_not_conflicting_with_pipeline(self, auth_session):
        """GET /api/meetings/pipeline should still work (not matched as {meeting_id}/proposal.pdf)"""
        response = auth_session.get(f"{BASE_URL}/api/meetings/pipeline")
        assert response.status_code == 200
        assert "by_stage" in response.json()
    
    def test_proposal_pdf_route_not_conflicting_with_analytics(self, auth_session):
        """GET /api/meetings/analytics should still work"""
        response = auth_session.get(f"{BASE_URL}/api/meetings/analytics")
        assert response.status_code == 200
        assert "funnel" in response.json()


# ==================== REGRESSION TESTS (from iteration 278) ====================

class TestRegressionOwnerPortalPDF:
    """Regression: Owner Portal PDF still works"""
    
    def test_owner_pdf_endpoint_still_works(self, auth_session):
        """GET /api/owners/{owner_id}/statement.pdf still returns PDF"""
        # First create an owner
        owner_resp = auth_session.post(f"{BASE_URL}/api/owners", json={
            "name": "TEST_Regression_Owner",
            "email": "regression_owner@test.com",
            "management_fee_percent": 15.0
        })
        if owner_resp.status_code != 200:
            pytest.skip("Could not create owner for regression test")
        
        owner_id = owner_resp.json()["id"]
        month = datetime.now().strftime("%Y-%m")
        
        response = auth_session.get(f"{BASE_URL}/api/owners/{owner_id}/statement.pdf?month={month}")
        assert response.status_code == 200
        assert "application/pdf" in response.headers.get("Content-Type", "")
        assert response.content[:4] == b'%PDF'
        print("Owner PDF regression test passed")


class TestRegressionMeetingsCRUD:
    """Regression: Meetings CRUD still works"""
    
    def test_list_meetings(self, auth_session):
        """GET /api/meetings returns list structure"""
        response = auth_session.get(f"{BASE_URL}/api/meetings")
        assert response.status_code == 200
        data = response.json()
        assert "meetings" in data
        assert "count" in data
        assert "stages" in data
    
    def test_create_meeting(self, auth_session):
        """POST /api/meetings creates meeting"""
        response = auth_session.post(f"{BASE_URL}/api/meetings", json={
            "name": "TEST_Regression_Meeting",
            "event_type": "wedding",
            "property_id": "default",
            "event_date": "2027-02-14"
        })
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["stage"] == "inquiry"
        TestRegressionMeetingsCRUD.meeting_id = data["id"]
    
    def test_get_meeting_detail(self, auth_session):
        """GET /api/meetings/{id} returns detail"""
        meeting_id = getattr(TestRegressionMeetingsCRUD, 'meeting_id', None)
        if not meeting_id:
            pytest.skip("No meeting_id")
        
        response = auth_session.get(f"{BASE_URL}/api/meetings/{meeting_id}")
        assert response.status_code == 200
        assert "items" in response.json()
        assert "total_estimate" in response.json()
    
    def test_patch_meeting(self, auth_session):
        """PATCH /api/meetings/{id} updates meeting"""
        meeting_id = getattr(TestRegressionMeetingsCRUD, 'meeting_id', None)
        if not meeting_id:
            pytest.skip("No meeting_id")
        
        response = auth_session.patch(f"{BASE_URL}/api/meetings/{meeting_id}", json={
            "notes": "Updated notes"
        })
        assert response.status_code == 200
        assert response.json()["updated"] == True
    
    def test_add_line_item(self, auth_session):
        """POST /api/meetings/{id}/items adds item"""
        meeting_id = getattr(TestRegressionMeetingsCRUD, 'meeting_id', None)
        if not meeting_id:
            pytest.skip("No meeting_id")
        
        response = auth_session.post(f"{BASE_URL}/api/meetings/{meeting_id}/items", json={
            "kind": "fnb",
            "label": "Regression Test Item",
            "qty": 10,
            "unit_price": 50.0
        })
        assert response.status_code == 200
        assert response.json()["subtotal"] == 500.0
        TestRegressionMeetingsCRUD.item_id = response.json()["id"]
    
    def test_delete_line_item(self, auth_session):
        """DELETE /api/meetings/{id}/items/{item_id} removes item"""
        meeting_id = getattr(TestRegressionMeetingsCRUD, 'meeting_id', None)
        item_id = getattr(TestRegressionMeetingsCRUD, 'item_id', None)
        if not meeting_id or not item_id:
            pytest.skip("No meeting_id or item_id")
        
        response = auth_session.delete(f"{BASE_URL}/api/meetings/{meeting_id}/items/{item_id}")
        assert response.status_code == 200
        assert response.json()["deleted"] == 1


class TestRegressionMeetingsPipelineAnalytics:
    """Regression: Pipeline and Analytics still work"""
    
    def test_pipeline(self, auth_session):
        """GET /api/meetings/pipeline returns Kanban data"""
        response = auth_session.get(f"{BASE_URL}/api/meetings/pipeline")
        assert response.status_code == 200
        data = response.json()
        assert "by_stage" in data
        assert "active_value" in data
    
    def test_analytics(self, auth_session):
        """GET /api/meetings/analytics returns funnel data"""
        response = auth_session.get(f"{BASE_URL}/api/meetings/analytics?days=90")
        assert response.status_code == 200
        data = response.json()
        assert "funnel" in data
        assert "win_rate_pct" in data
        assert "won_revenue_estimate" in data


# ==================== CLEANUP ====================

class TestCleanup:
    """Cleanup test data"""
    
    def test_cleanup_test_meetings(self, auth_session):
        """Mark TEST_ prefixed meetings as lost for cleanup"""
        response = auth_session.get(f"{BASE_URL}/api/meetings")
        if response.status_code == 200:
            meetings = response.json().get("meetings", [])
            cleaned = 0
            for m in meetings:
                if m.get("name", "").startswith("TEST_"):
                    auth_session.patch(f"{BASE_URL}/api/meetings/{m['id']}", json={
                        "stage": "lost",
                        "lost_reason": "test_cleanup_iter279"
                    })
                    cleaned += 1
            print(f"Cleaned up {cleaned} test meetings")
