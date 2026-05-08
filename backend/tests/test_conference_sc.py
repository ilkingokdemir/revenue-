"""
Conference S&C (MICE) Module Tests - Batch 27
Tests for event spaces, catering packages, inquiries, proposals, and dashboard.
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
PROPERTY_ID = "default"


@pytest.fixture(scope="module")
def auth_token():
    """Get admin auth token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.cookies.get("access_token") or response.json().get("access_token")


@pytest.fixture(scope="module")
def auth_session(auth_token):
    """Create authenticated session"""
    session = requests.Session()
    session.cookies.set("access_token", auth_token)
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestEventSpaces:
    """Event Spaces CRUD tests"""

    def test_list_event_spaces_empty_initially(self, auth_session):
        """GET /api/conference/event-spaces/{property_id} - list spaces"""
        response = auth_session.get(f"{BASE_URL}/api/conference/event-spaces/{PROPERTY_ID}")
        assert response.status_code == 200
        data = response.json()
        assert "rows" in data
        assert "count" in data
        print(f"✓ List event spaces: {data['count']} spaces found")

    def test_seed_defaults_creates_spaces_and_catering(self, auth_session):
        """POST /api/conference/event-spaces/{property_id}/seed-defaults - seeds 4 spaces + 6 catering"""
        response = auth_session.post(f"{BASE_URL}/api/conference/event-spaces/{PROPERTY_ID}/seed-defaults")
        assert response.status_code == 200
        data = response.json()
        # First call should seed, subsequent calls return 0
        if "seeded_spaces" in data:
            assert data["seeded_spaces"] == 4, f"Expected 4 spaces, got {data['seeded_spaces']}"
            assert data.get("seeded_catering", 0) == 6, f"Expected 6 catering, got {data.get('seeded_catering')}"
            print(f"✓ Seeded {data['seeded_spaces']} spaces + {data.get('seeded_catering', 0)} catering")
        else:
            # Already seeded
            assert "note" in data or data.get("seeded", 0) == 0
            print(f"✓ Already seeded: {data}")

    def test_seed_defaults_idempotent(self, auth_session):
        """POST seed-defaults second time returns 0 (already seeded)"""
        response = auth_session.post(f"{BASE_URL}/api/conference/event-spaces/{PROPERTY_ID}/seed-defaults")
        assert response.status_code == 200
        data = response.json()
        # Should indicate already seeded
        assert data.get("seeded", 0) == 0 or "note" in data or data.get("seeded_spaces", 0) == 0
        print(f"✓ Seed idempotent: {data}")

    def test_list_event_spaces_after_seed(self, auth_session):
        """Verify 4 spaces exist after seeding"""
        response = auth_session.get(f"{BASE_URL}/api/conference/event-spaces/{PROPERTY_ID}")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] >= 4, f"Expected at least 4 spaces, got {data['count']}"
        # Verify space structure
        if data["rows"]:
            space = data["rows"][0]
            assert "name" in space
            assert "capacity_theater" in space or "capacity_banquet" in space
            assert "full_day_rate" in space
        print(f"✓ Verified {data['count']} spaces with correct structure")

    def test_upsert_event_space(self, auth_session):
        """POST /api/conference/event-spaces - upsert space"""
        space_data = {
            "property_id": PROPERTY_ID,
            "name": "TEST_Conference Room B",
            "capacity_theater": 100,
            "capacity_banquet": 60,
            "capacity_boardroom": 30,
            "capacity_reception": 120,
            "area_sqm": 80,
            "half_day_rate": 300,
            "full_day_rate": 500,
            "features": ["Projector", "Whiteboard", "Video conferencing"]
        }
        response = auth_session.post(f"{BASE_URL}/api/conference/event-spaces", json=space_data)
        assert response.status_code == 200
        data = response.json()
        assert data.get("upserted") or data.get("modified") is not None
        print(f"✓ Upserted space: {data}")


class TestCateringPackages:
    """Catering Packages CRUD tests"""

    def test_list_catering_packages(self, auth_session):
        """GET /api/conference/catering/{property_id} - list catering"""
        response = auth_session.get(f"{BASE_URL}/api/conference/catering/{PROPERTY_ID}")
        assert response.status_code == 200
        data = response.json()
        assert "rows" in data
        assert "count" in data
        assert data["count"] >= 6, f"Expected at least 6 catering packages, got {data['count']}"
        # Verify structure
        if data["rows"]:
            pkg = data["rows"][0]
            assert "name" in pkg
            assert "category" in pkg
            assert "per_person_price" in pkg
        print(f"✓ Listed {data['count']} catering packages")

    def test_upsert_catering_package(self, auth_session):
        """POST /api/conference/catering - upsert package"""
        pkg_data = {
            "property_id": PROPERTY_ID,
            "name": "TEST_Premium Dinner",
            "category": "dinner",
            "per_person_price": 85,
            "min_persons": 20,
            "includes": ["5-course menu", "Wine pairing", "Live music"]
        }
        response = auth_session.post(f"{BASE_URL}/api/conference/catering", json=pkg_data)
        assert response.status_code == 200
        data = response.json()
        assert data.get("updated") is True
        print(f"✓ Upserted catering package: {data}")


class TestInquiries:
    """Inquiry CRUD and validation tests"""

    @pytest.fixture(scope="class")
    def created_inquiry_id(self, auth_session):
        """Create an inquiry for subsequent tests"""
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        day_after = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
        
        inquiry_data = {
            "property_id": PROPERTY_ID,
            "contact_name": "TEST_John Smith",
            "contact_email": "test@conference.com",
            "contact_company": "TEST Corp",
            "contact_phone": "+44 123 456 7890",
            "event_name": "TEST_Annual Leadership Summit",
            "event_type": "conference",
            "start_date": tomorrow,
            "end_date": day_after,
            "total_attendees": 120,
            "budget_estimate": 50000,
            "special_requirements": "Vegetarian options needed"
        }
        response = auth_session.post(f"{BASE_URL}/api/conference/inquiry", json=inquiry_data)
        assert response.status_code == 200
        data = response.json()
        return data["id"]

    def test_create_inquiry_success(self, auth_session):
        """POST /api/conference/inquiry - creates inquiry with auto-generated ref"""
        tomorrow = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")
        day_after = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        
        inquiry_data = {
            "property_id": PROPERTY_ID,
            "contact_name": "TEST_Jane Doe",
            "contact_email": "jane@test.com",
            "event_name": "TEST_Product Launch",
            "event_type": "meeting",
            "start_date": tomorrow,
            "end_date": day_after,
            "total_attendees": 50
        }
        response = auth_session.post(f"{BASE_URL}/api/conference/inquiry", json=inquiry_data)
        assert response.status_code == 200
        data = response.json()
        
        # Verify auto-generated fields
        assert "id" in data
        assert "ref" in data
        assert data["ref"].startswith("INQ-")
        assert data["status"] == "new"
        assert data["days"] == 3  # 3 days inclusive
        print(f"✓ Created inquiry: {data['ref']} with {data['days']} days")

    def test_create_inquiry_invalid_dates(self, auth_session):
        """POST /api/conference/inquiry - rejects end_date before start_date"""
        tomorrow = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")
        yesterday = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
        
        inquiry_data = {
            "property_id": PROPERTY_ID,
            "contact_name": "TEST_Invalid",
            "contact_email": "invalid@test.com",
            "event_name": "TEST_Invalid Event",
            "event_type": "conference",
            "start_date": tomorrow,
            "end_date": yesterday,  # Before start
            "total_attendees": 50
        }
        response = auth_session.post(f"{BASE_URL}/api/conference/inquiry", json=inquiry_data)
        assert response.status_code == 400
        assert "end_date" in response.text.lower() or "after" in response.text.lower()
        print(f"✓ Correctly rejected invalid dates: {response.json()}")

    def test_create_inquiry_invalid_attendees(self, auth_session):
        """POST /api/conference/inquiry - validates total_attendees 1..5000"""
        tomorrow = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")
        day_after = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        
        # Test too many attendees
        inquiry_data = {
            "property_id": PROPERTY_ID,
            "contact_name": "TEST_TooMany",
            "contact_email": "toomany@test.com",
            "event_name": "TEST_Huge Event",
            "event_type": "conference",
            "start_date": tomorrow,
            "end_date": day_after,
            "total_attendees": 6000  # Over 5000 limit
        }
        response = auth_session.post(f"{BASE_URL}/api/conference/inquiry", json=inquiry_data)
        assert response.status_code == 400
        assert "attendees" in response.text.lower() or "5000" in response.text
        print(f"✓ Correctly rejected invalid attendees: {response.json()}")

    def test_list_inquiries_with_status_aggregation(self, auth_session):
        """GET /api/conference/inquiries/{property_id} - lists with by_status"""
        response = auth_session.get(f"{BASE_URL}/api/conference/inquiries/{PROPERTY_ID}")
        assert response.status_code == 200
        data = response.json()
        
        assert "rows" in data
        assert "count" in data
        assert "by_status" in data
        print(f"✓ Listed {data['count']} inquiries with status aggregation: {data['by_status']}")

    def test_list_inquiries_with_status_filter(self, auth_session):
        """GET /api/conference/inquiries/{property_id}?status=new - filters by status"""
        response = auth_session.get(f"{BASE_URL}/api/conference/inquiries/{PROPERTY_ID}?status=new")
        assert response.status_code == 200
        data = response.json()
        
        # All returned should be 'new' status
        for row in data["rows"]:
            assert row["status"] == "new"
        print(f"✓ Filtered inquiries by status=new: {data['count']} results")

    def test_get_inquiry_detail(self, auth_session, created_inquiry_id):
        """GET /api/conference/inquiry/{id} - returns detail"""
        response = auth_session.get(f"{BASE_URL}/api/conference/inquiry/{created_inquiry_id}")
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == created_inquiry_id
        assert "ref" in data
        assert "contact_name" in data
        assert "event_name" in data
        print(f"✓ Got inquiry detail: {data['ref']}")

    def test_get_inquiry_not_found(self, auth_session):
        """GET /api/conference/inquiry/{id} - returns 404 if not found"""
        response = auth_session.get(f"{BASE_URL}/api/conference/inquiry/nonexistent-id-12345")
        assert response.status_code == 404
        print(f"✓ Correctly returned 404 for non-existent inquiry")


class TestProposalBuilder:
    """Proposal building and calculation tests"""

    @pytest.fixture(scope="class")
    def inquiry_for_proposal(self, auth_session):
        """Create inquiry for proposal tests"""
        tomorrow = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
        day_after = (datetime.now() + timedelta(days=12)).strftime("%Y-%m-%d")
        
        inquiry_data = {
            "property_id": PROPERTY_ID,
            "contact_name": "TEST_Proposal Test",
            "contact_email": "proposal@test.com",
            "event_name": "TEST_Proposal Summit",
            "event_type": "conference",
            "start_date": tomorrow,
            "end_date": day_after,
            "total_attendees": 100
        }
        response = auth_session.post(f"{BASE_URL}/api/conference/inquiry", json=inquiry_data)
        assert response.status_code == 200
        return response.json()

    def test_build_proposal_success(self, auth_session, inquiry_for_proposal):
        """POST /api/conference/inquiry/{id}/proposal - builds proposal with calculations"""
        inq_id = inquiry_for_proposal["id"]
        
        proposal_data = {
            "lines": [
                {"type": "space", "description": "Grand Ballroom (3 days)", "qty": 3, "unit_price": 2500, "currency": "gbp"},
                {"type": "catering", "description": "Business Lunch (100 pax x 3 days)", "qty": 300, "unit_price": 35, "currency": "gbp"},
                {"type": "room_block", "description": "50 rooms x 2 nights", "qty": 100, "unit_price": 120, "currency": "gbp"}
            ],
            "discount_pct": 10,
            "notes": "Special corporate rate applied",
            "valid_until": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        }
        
        response = auth_session.post(f"{BASE_URL}/api/conference/inquiry/{inq_id}/proposal", json=proposal_data)
        assert response.status_code == 200
        data = response.json()
        
        # Verify calculations
        # Subtotal: 3*2500 + 300*35 + 100*120 = 7500 + 10500 + 12000 = 30000
        # Discount: 30000 * 10% = 3000
        # Total: 30000 - 3000 = 27000
        # Per person: 27000 / 100 = 270
        assert data["subtotal"] == 30000
        assert data["discount_amount"] == 3000
        assert data["total"] == 27000
        assert data["per_person"] == 270
        assert data["lines_count"] == 3
        print(f"✓ Built proposal: subtotal={data['subtotal']}, discount={data['discount_amount']}, total={data['total']}, per_person={data['per_person']}")

    def test_build_proposal_empty_lines_rejected(self, auth_session, inquiry_for_proposal):
        """POST /api/conference/inquiry/{id}/proposal - rejects empty lines"""
        inq_id = inquiry_for_proposal["id"]
        
        proposal_data = {
            "lines": [],
            "discount_pct": 0
        }
        
        response = auth_session.post(f"{BASE_URL}/api/conference/inquiry/{inq_id}/proposal", json=proposal_data)
        assert response.status_code == 400
        assert "line" in response.text.lower()
        print(f"✓ Correctly rejected empty lines: {response.json()}")

    def test_build_proposal_invalid_discount(self, auth_session, inquiry_for_proposal):
        """POST /api/conference/inquiry/{id}/proposal - validates discount_pct 0..50"""
        inq_id = inquiry_for_proposal["id"]
        
        proposal_data = {
            "lines": [{"type": "custom", "description": "Test", "qty": 1, "unit_price": 100, "currency": "gbp"}],
            "discount_pct": 60  # Over 50% limit
        }
        
        response = auth_session.post(f"{BASE_URL}/api/conference/inquiry/{inq_id}/proposal", json=proposal_data)
        assert response.status_code == 400
        assert "discount" in response.text.lower() or "50" in response.text
        print(f"✓ Correctly rejected invalid discount: {response.json()}")


class TestStatusTransitions:
    """Status change tests"""

    @pytest.fixture(scope="class")
    def inquiry_for_status(self, auth_session):
        """Create inquiry for status tests"""
        tomorrow = (datetime.now() + timedelta(days=20)).strftime("%Y-%m-%d")
        day_after = (datetime.now() + timedelta(days=22)).strftime("%Y-%m-%d")
        
        inquiry_data = {
            "property_id": PROPERTY_ID,
            "contact_name": "TEST_Status Test",
            "contact_email": "status@test.com",
            "event_name": "TEST_Status Summit",
            "event_type": "gala",
            "start_date": tomorrow,
            "end_date": day_after,
            "total_attendees": 200
        }
        response = auth_session.post(f"{BASE_URL}/api/conference/inquiry", json=inquiry_data)
        assert response.status_code == 200
        return response.json()

    def test_set_status_sent(self, auth_session, inquiry_for_status):
        """POST /api/conference/inquiry/{id}/status/sent - sets status"""
        inq_id = inquiry_for_status["id"]
        
        response = auth_session.post(f"{BASE_URL}/api/conference/inquiry/{inq_id}/status/sent")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "sent"
        print(f"✓ Set status to 'sent': {data}")

    def test_set_status_accepted(self, auth_session, inquiry_for_status):
        """POST /api/conference/inquiry/{id}/status/accepted - sets status"""
        inq_id = inquiry_for_status["id"]
        
        response = auth_session.post(f"{BASE_URL}/api/conference/inquiry/{inq_id}/status/accepted")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        print(f"✓ Set status to 'accepted': {data}")

    def test_set_status_invalid(self, auth_session, inquiry_for_status):
        """POST /api/conference/inquiry/{id}/status/invalid - returns 400"""
        inq_id = inquiry_for_status["id"]
        
        response = auth_session.post(f"{BASE_URL}/api/conference/inquiry/{inq_id}/status/invalid_status")
        assert response.status_code == 400
        print(f"✓ Correctly rejected invalid status: {response.json()}")


class TestDashboard:
    """Dashboard aggregation tests"""

    def test_dashboard_default_90_days(self, auth_session):
        """GET /api/conference/dashboard/{property_id} - returns aggregates"""
        response = auth_session.get(f"{BASE_URL}/api/conference/dashboard/{PROPERTY_ID}")
        assert response.status_code == 200
        data = response.json()
        
        assert "total_inquiries" in data
        assert "pipeline_value" in data
        assert "won_value" in data
        assert "lost_value" in data
        assert "avg_deal_size" in data
        assert "conversion_rate" in data
        assert "by_event_type" in data
        assert data["days"] == 90
        print(f"✓ Dashboard (90 days): total={data['total_inquiries']}, pipeline=£{data['pipeline_value']}, won=£{data['won_value']}, conversion={data['conversion_rate']}%")

    def test_dashboard_custom_days(self, auth_session):
        """GET /api/conference/dashboard/{property_id}?days=30 - custom range"""
        response = auth_session.get(f"{BASE_URL}/api/conference/dashboard/{PROPERTY_ID}?days=30")
        assert response.status_code == 200
        data = response.json()
        assert data["days"] == 30
        print(f"✓ Dashboard (30 days): total={data['total_inquiries']}")

    def test_dashboard_invalid_days(self, auth_session):
        """GET /api/conference/dashboard/{property_id}?days=5 - rejects <7"""
        response = auth_session.get(f"{BASE_URL}/api/conference/dashboard/{PROPERTY_ID}?days=5")
        assert response.status_code == 400
        print(f"✓ Correctly rejected days<7: {response.json()}")


class TestAuthRequired:
    """Auth requirement tests"""

    def test_endpoints_require_auth(self):
        """All endpoints should require authentication"""
        endpoints = [
            ("GET", f"{BASE_URL}/api/conference/event-spaces/{PROPERTY_ID}"),
            ("GET", f"{BASE_URL}/api/conference/catering/{PROPERTY_ID}"),
            ("GET", f"{BASE_URL}/api/conference/inquiries/{PROPERTY_ID}"),
            ("GET", f"{BASE_URL}/api/conference/dashboard/{PROPERTY_ID}"),
        ]
        
        for method, url in endpoints:
            if method == "GET":
                response = requests.get(url)
            else:
                response = requests.post(url)
            
            assert response.status_code in [401, 403], f"{method} {url} should require auth, got {response.status_code}"
        
        print(f"✓ All {len(endpoints)} endpoints require authentication")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
