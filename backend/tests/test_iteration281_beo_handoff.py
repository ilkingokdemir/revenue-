"""
Iteration 281 - MICE → BEO One-Click Handoff Tests

Tests for POST /api/meetings/{id}/generate-beo endpoint:
1. Returns 400 for inquiry stage meetings
2. Returns success for confirmed+ meetings with correct BEO structure
3. Idempotent - re-running returns created:false
4. BEO document has correct fields from meeting
5. Meeting record gets beo_id and beo_generated_at stamped
6. 404 on non-existent meeting_id
7. Regression tests for iter 277-280 features
"""

import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

@pytest.fixture(scope="module")
def auth_session():
    """Get authenticated session"""
    session = requests.Session()
    login_resp = session.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"}
    )
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    return session


class TestBEOGeneration:
    """Tests for the new BEO generation endpoint"""
    
    @pytest.fixture(scope="class")
    def test_meeting_inquiry(self, auth_session):
        """Create a test meeting in inquiry stage"""
        meeting_data = {
            "name": f"TEST_BEO_Inquiry_{uuid.uuid4().hex[:8]}",
            "event_type": "wedding",
            "property_id": "default",
            "contact_name": "Test Client",
            "contact_email": "test@example.com",
            "contact_phone": "+44123456789",
            "event_date": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
            "guests_count": 100,
            "rooms_required": 20,
            "budget_estimate": 15000,
            "notes": "Special dietary requirements: vegetarian options needed"
        }
        resp = auth_session.post(f"{BASE_URL}/api/meetings", json=meeting_data)
        assert resp.status_code == 200, f"Failed to create meeting: {resp.text}"
        meeting = resp.json()
        assert meeting["stage"] == "inquiry"
        yield meeting
        # Cleanup - no explicit delete endpoint, but meeting will be TEST_ prefixed
    
    @pytest.fixture(scope="class")
    def test_meeting_confirmed(self, auth_session):
        """Create a test meeting and move to confirmed stage with line items"""
        # Create meeting
        meeting_data = {
            "name": f"TEST_BEO_Confirmed_{uuid.uuid4().hex[:8]}",
            "event_type": "corporate_meeting",
            "property_id": "default",
            "contact_name": "Corporate Client",
            "contact_email": "corp@example.com",
            "contact_phone": "+44987654321",
            "event_date": (datetime.now() + timedelta(days=60)).strftime("%Y-%m-%d"),
            "guests_count": 50,
            "rooms_required": 10,
            "budget_estimate": 8000,
            "notes": "AV equipment required for presentations"
        }
        resp = auth_session.post(f"{BASE_URL}/api/meetings", json=meeting_data)
        assert resp.status_code == 200, f"Failed to create meeting: {resp.text}"
        meeting = resp.json()
        meeting_id = meeting["id"]
        
        # Add line items - fnb, av_tech, meeting_space, and bar item
        items = [
            {"kind": "fnb", "label": "Lunch Buffet", "qty": 50, "unit_price": 35},
            {"kind": "fnb", "label": "Open Bar Service", "qty": 50, "unit_price": 25},  # Contains 'bar'
            {"kind": "av_tech", "label": "Projector + Screen", "qty": 1, "unit_price": 200},
            {"kind": "av_tech", "label": "Microphone System", "qty": 2, "unit_price": 75},
            {"kind": "meeting_space", "label": "Grand Ballroom", "qty": 1, "unit_price": 1500},
        ]
        for item in items:
            item_resp = auth_session.post(f"{BASE_URL}/api/meetings/{meeting_id}/items", json=item)
            assert item_resp.status_code == 200, f"Failed to add item: {item_resp.text}"
        
        # Move to confirmed stage
        patch_resp = auth_session.patch(f"{BASE_URL}/api/meetings/{meeting_id}", json={"stage": "confirmed"})
        assert patch_resp.status_code == 200, f"Failed to move to confirmed: {patch_resp.text}"
        
        # Get updated meeting
        get_resp = auth_session.get(f"{BASE_URL}/api/meetings/{meeting_id}")
        assert get_resp.status_code == 200
        meeting = get_resp.json()
        assert meeting["stage"] == "confirmed"
        
        yield meeting
    
    def test_beo_generation_inquiry_returns_400(self, auth_session, test_meeting_inquiry):
        """BEO generation on inquiry stage meeting should return 400"""
        meeting_id = test_meeting_inquiry["id"]
        resp = auth_session.post(f"{BASE_URL}/api/meetings/{meeting_id}/generate-beo")
        
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "confirmed" in data.get("detail", "").lower() or "only" in data.get("detail", "").lower()
        print(f"PASS: Inquiry stage meeting correctly rejected with 400: {data.get('detail')}")
    
    def test_beo_generation_confirmed_success(self, auth_session, test_meeting_confirmed):
        """BEO generation on confirmed meeting should succeed"""
        meeting_id = test_meeting_confirmed["id"]
        resp = auth_session.post(f"{BASE_URL}/api/meetings/{meeting_id}/generate-beo")
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        # Verify response structure
        assert "beo_id" in data, "Response should contain beo_id"
        assert data.get("created") == True, "First generation should have created=True"
        assert "menu_items" in data, "Response should contain menu_items count"
        assert "av_items" in data, "Response should contain av_items count"
        assert "beverage_items" in data, "Response should contain beverage_items count"
        
        # Verify counts
        assert data["menu_items"] >= 1, "Should have at least 1 menu item (Lunch Buffet)"
        assert data["av_items"] == 2, "Should have 2 AV items"
        assert data["beverage_items"] >= 1, "Should have at least 1 beverage item (Open Bar)"
        
        print(f"PASS: BEO generated successfully - beo_id={data['beo_id']}, menu={data['menu_items']}, av={data['av_items']}, bev={data['beverage_items']}")
        return data["beo_id"]
    
    def test_beo_generation_idempotent(self, auth_session, test_meeting_confirmed):
        """Re-running BEO generation should return created=False"""
        meeting_id = test_meeting_confirmed["id"]
        
        # First call (may already be created from previous test)
        resp1 = auth_session.post(f"{BASE_URL}/api/meetings/{meeting_id}/generate-beo")
        assert resp1.status_code == 200
        
        # Second call - should be idempotent
        resp2 = auth_session.post(f"{BASE_URL}/api/meetings/{meeting_id}/generate-beo")
        assert resp2.status_code == 200, f"Expected 200, got {resp2.status_code}: {resp2.text}"
        data = resp2.json()
        
        assert data.get("created") == False, "Second call should have created=False"
        assert "already exists" in data.get("note", "").lower() or "beo_id" in data
        print(f"PASS: Idempotent behavior verified - created=False, note={data.get('note')}")
    
    def test_meeting_stamped_with_beo_id(self, auth_session, test_meeting_confirmed):
        """Meeting record should have beo_id and beo_generated_at after generation"""
        meeting_id = test_meeting_confirmed["id"]
        
        # Ensure BEO is generated
        auth_session.post(f"{BASE_URL}/api/meetings/{meeting_id}/generate-beo")
        
        # Get meeting and verify stamps
        resp = auth_session.get(f"{BASE_URL}/api/meetings/{meeting_id}")
        assert resp.status_code == 200
        meeting = resp.json()
        
        assert "beo_id" in meeting and meeting["beo_id"], "Meeting should have beo_id stamped"
        assert "beo_generated_at" in meeting and meeting["beo_generated_at"], "Meeting should have beo_generated_at stamped"
        
        # Verify beo_generated_at is a valid ISO timestamp
        try:
            datetime.fromisoformat(meeting["beo_generated_at"].replace("Z", "+00:00"))
        except ValueError:
            pytest.fail(f"beo_generated_at is not valid ISO format: {meeting['beo_generated_at']}")
        
        print(f"PASS: Meeting stamped - beo_id={meeting['beo_id']}, beo_generated_at={meeting['beo_generated_at']}")
    
    def test_beo_document_structure(self, auth_session, test_meeting_confirmed):
        """Verify BEO document has correct structure and values from meeting"""
        meeting_id = test_meeting_confirmed["id"]
        meeting = test_meeting_confirmed
        
        # Generate BEO
        gen_resp = auth_session.post(f"{BASE_URL}/api/meetings/{meeting_id}/generate-beo")
        assert gen_resp.status_code == 200
        beo_id = gen_resp.json()["beo_id"]
        
        # Get BEO document from banquet_orders endpoint
        beo_resp = auth_session.get(f"{BASE_URL}/api/banquet-orders/single/{beo_id}")
        assert beo_resp.status_code == 200, f"Failed to get BEO: {beo_resp.text}"
        beo = beo_resp.json()
        
        # Verify BEO fields match meeting data
        assert beo.get("event_name") == meeting["name"], f"event_name mismatch: {beo.get('event_name')} != {meeting['name']}"
        assert beo.get("event_date") == meeting["event_date"], f"event_date mismatch"
        assert beo.get("guest_count") == meeting["guests_count"], f"guest_count mismatch"
        assert beo.get("status") == "draft", f"status should be 'draft', got {beo.get('status')}"
        assert beo.get("proposal_id") == meeting_id, f"proposal_id should be meeting_id"
        
        # Verify venue_room from meeting_space item
        assert beo.get("venue_room") == "Grand Ballroom", f"venue_room should be 'Grand Ballroom', got {beo.get('venue_room')}"
        
        # Verify contacts (should have 2: Client + Sales Lead)
        contacts = beo.get("contacts", [])
        assert len(contacts) == 2, f"Should have 2 contacts, got {len(contacts)}"
        client_contact = next((c for c in contacts if c.get("role") == "Client"), None)
        assert client_contact, "Should have Client contact"
        assert client_contact.get("name") == meeting["contact_name"]
        
        # Verify special_requests from meeting.notes
        assert beo.get("special_requests") == meeting["notes"], f"special_requests should match meeting notes"
        
        # Verify billing_instructions includes total
        billing = beo.get("billing_instructions", "")
        assert "total" in billing.lower() or "£" in billing, f"billing_instructions should include total"
        
        print(f"PASS: BEO document structure verified - event_name={beo['event_name']}, venue={beo['venue_room']}, contacts={len(contacts)}")
    
    def test_beo_generation_404_nonexistent(self, auth_session):
        """BEO generation on non-existent meeting should return 404"""
        fake_id = f"nonexistent-{uuid.uuid4().hex}"
        resp = auth_session.post(f"{BASE_URL}/api/meetings/{fake_id}/generate-beo")
        
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"
        print(f"PASS: Non-existent meeting correctly returns 404")


class TestRegressionIter277to280:
    """Regression tests for features from iterations 277-280"""
    
    def test_meetings_list(self, auth_session):
        """Verify meetings list endpoint still works"""
        resp = auth_session.get(f"{BASE_URL}/api/meetings")
        assert resp.status_code == 200, f"Meetings list failed: {resp.text}"
        data = resp.json()
        assert "meetings" in data
        assert "stages" in data
        print(f"PASS: Meetings list - {data.get('count', 0)} meetings")
    
    def test_meetings_pipeline(self, auth_session):
        """Verify meetings pipeline endpoint still works"""
        resp = auth_session.get(f"{BASE_URL}/api/meetings/pipeline")
        assert resp.status_code == 200, f"Pipeline failed: {resp.text}"
        data = resp.json()
        assert "by_stage" in data
        assert "active_value" in data
        print(f"PASS: Pipeline - active_value=£{data.get('active_value', 0)}")
    
    def test_meetings_analytics(self, auth_session):
        """Verify meetings analytics endpoint still works"""
        resp = auth_session.get(f"{BASE_URL}/api/meetings/analytics")
        assert resp.status_code == 200, f"Analytics failed: {resp.text}"
        data = resp.json()
        assert "funnel" in data
        assert "win_rate_pct" in data
        print(f"PASS: Analytics - win_rate={data.get('win_rate_pct')}%")
    
    def test_proposal_pdf_endpoint(self, auth_session):
        """Verify proposal PDF endpoint still works (iter 279)"""
        # Get a meeting with items
        meetings_resp = auth_session.get(f"{BASE_URL}/api/meetings")
        assert meetings_resp.status_code == 200
        meetings = meetings_resp.json().get("meetings", [])
        
        if not meetings:
            pytest.skip("No meetings available for PDF test")
        
        meeting_id = meetings[0]["id"]
        resp = auth_session.get(f"{BASE_URL}/api/meetings/{meeting_id}/proposal.pdf")
        assert resp.status_code == 200, f"Proposal PDF failed: {resp.text}"
        assert resp.headers.get("content-type") == "application/pdf"
        print(f"PASS: Proposal PDF endpoint works")
    
    def test_fnb_pos_providers(self, auth_session):
        """Verify F&B POS providers endpoint still works (iter 280)"""
        resp = auth_session.get(f"{BASE_URL}/api/fnb-pos/providers")
        assert resp.status_code == 200, f"FnB POS providers failed: {resp.text}"
        data = resp.json()
        assert "providers" in data
        assert len(data["providers"]) >= 5
        print(f"PASS: F&B POS providers - {len(data['providers'])} providers")
    
    def test_fnb_pos_connections(self, auth_session):
        """Verify F&B POS connections endpoint still works (iter 280)"""
        resp = auth_session.get(f"{BASE_URL}/api/fnb-pos/connections")
        assert resp.status_code == 200, f"FnB POS connections failed: {resp.text}"
        print(f"PASS: F&B POS connections endpoint works")
    
    def test_banquet_orders_list(self, auth_session):
        """Verify banquet orders list endpoint still works"""
        resp = auth_session.get(f"{BASE_URL}/api/banquet-orders/default")
        assert resp.status_code == 200, f"Banquet orders list failed: {resp.text}"
        data = resp.json()
        assert "items" in data or "count" in data
        print(f"PASS: Banquet orders list works - {data.get('count', 0)} orders")
    
    def test_channel_parity(self, auth_session):
        """Verify channel parity endpoint still works"""
        resp = auth_session.get(f"{BASE_URL}/api/channel-parity/default")
        assert resp.status_code == 200, f"Channel parity failed: {resp.text}"
        print(f"PASS: Channel parity works")
    
    def test_spa_services(self, auth_session):
        """Verify spa services endpoint still works (iter 278)"""
        resp = auth_session.get(f"{BASE_URL}/api/spa/services")
        assert resp.status_code == 200, f"Spa services failed: {resp.text}"
        print(f"PASS: Spa services works")


class TestBEOEdgeCases:
    """Edge case tests for BEO generation"""
    
    def test_beo_generation_invoiced_stage(self, auth_session):
        """BEO generation should work for invoiced stage meetings"""
        # Create meeting
        meeting_data = {
            "name": f"TEST_BEO_Invoiced_{uuid.uuid4().hex[:8]}",
            "event_type": "gala",
            "property_id": "default",
            "contact_name": "Gala Client",
            "contact_email": "gala@example.com",
            "event_date": (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d"),
            "guests_count": 200,
        }
        create_resp = auth_session.post(f"{BASE_URL}/api/meetings", json=meeting_data)
        assert create_resp.status_code == 200
        meeting_id = create_resp.json()["id"]
        
        # Move to invoiced stage
        auth_session.patch(f"{BASE_URL}/api/meetings/{meeting_id}", json={"stage": "invoiced"})
        
        # Generate BEO
        resp = auth_session.post(f"{BASE_URL}/api/meetings/{meeting_id}/generate-beo")
        assert resp.status_code == 200, f"BEO generation for invoiced stage failed: {resp.text}"
        assert resp.json().get("created") == True
        print(f"PASS: BEO generation works for invoiced stage")
    
    def test_beo_generation_completed_stage(self, auth_session):
        """BEO generation should work for completed stage meetings"""
        # Create meeting
        meeting_data = {
            "name": f"TEST_BEO_Completed_{uuid.uuid4().hex[:8]}",
            "event_type": "training",
            "property_id": "default",
            "contact_name": "Training Client",
            "contact_email": "training@example.com",
            "event_date": (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d"),
            "guests_count": 30,
        }
        create_resp = auth_session.post(f"{BASE_URL}/api/meetings", json=meeting_data)
        assert create_resp.status_code == 200
        meeting_id = create_resp.json()["id"]
        
        # Move to completed stage
        auth_session.patch(f"{BASE_URL}/api/meetings/{meeting_id}", json={"stage": "completed"})
        
        # Generate BEO
        resp = auth_session.post(f"{BASE_URL}/api/meetings/{meeting_id}/generate-beo")
        assert resp.status_code == 200, f"BEO generation for completed stage failed: {resp.text}"
        assert resp.json().get("created") == True
        print(f"PASS: BEO generation works for completed stage")
    
    def test_beo_generation_no_items(self, auth_session):
        """BEO generation should work even with no line items"""
        # Create meeting
        meeting_data = {
            "name": f"TEST_BEO_NoItems_{uuid.uuid4().hex[:8]}",
            "event_type": "birthday",
            "property_id": "default",
            "contact_name": "Birthday Client",
            "contact_email": "birthday@example.com",
            "event_date": (datetime.now() + timedelta(days=45)).strftime("%Y-%m-%d"),
            "guests_count": 25,
        }
        create_resp = auth_session.post(f"{BASE_URL}/api/meetings", json=meeting_data)
        assert create_resp.status_code == 200
        meeting_id = create_resp.json()["id"]
        
        # Move to confirmed stage (no items added)
        auth_session.patch(f"{BASE_URL}/api/meetings/{meeting_id}", json={"stage": "confirmed"})
        
        # Generate BEO
        resp = auth_session.post(f"{BASE_URL}/api/meetings/{meeting_id}/generate-beo")
        assert resp.status_code == 200, f"BEO generation with no items failed: {resp.text}"
        data = resp.json()
        assert data.get("created") == True
        assert data.get("menu_items") == 0
        assert data.get("av_items") == 0
        assert data.get("beverage_items") == 0
        print(f"PASS: BEO generation works with no line items")
    
    def test_beo_venue_room_tbd_when_no_space(self, auth_session):
        """BEO venue_room should be 'TBD' when no meeting_space item exists"""
        # Create meeting
        meeting_data = {
            "name": f"TEST_BEO_NoSpace_{uuid.uuid4().hex[:8]}",
            "event_type": "conference",
            "property_id": "default",
            "contact_name": "Conference Client",
            "event_date": (datetime.now() + timedelta(days=75)).strftime("%Y-%m-%d"),
            "guests_count": 80,
        }
        create_resp = auth_session.post(f"{BASE_URL}/api/meetings", json=meeting_data)
        assert create_resp.status_code == 200
        meeting_id = create_resp.json()["id"]
        
        # Add only fnb item (no meeting_space)
        auth_session.post(f"{BASE_URL}/api/meetings/{meeting_id}/items", json={
            "kind": "fnb", "label": "Coffee Break", "qty": 80, "unit_price": 5
        })
        
        # Move to confirmed
        auth_session.patch(f"{BASE_URL}/api/meetings/{meeting_id}", json={"stage": "confirmed"})
        
        # Generate BEO
        gen_resp = auth_session.post(f"{BASE_URL}/api/meetings/{meeting_id}/generate-beo")
        assert gen_resp.status_code == 200
        beo_id = gen_resp.json()["beo_id"]
        
        # Get BEO and verify venue_room is TBD
        beo_resp = auth_session.get(f"{BASE_URL}/api/banquet-orders/single/{beo_id}")
        assert beo_resp.status_code == 200
        beo = beo_resp.json()
        assert beo.get("venue_room") == "TBD", f"venue_room should be 'TBD', got {beo.get('venue_room')}"
        print(f"PASS: venue_room is 'TBD' when no meeting_space item")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
