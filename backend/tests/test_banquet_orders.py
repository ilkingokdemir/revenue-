"""
Banquet Event Orders (BEO) API Tests - Batch 37
Tests CRUD operations, PDF generation, dashboard, and validation
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
PROPERTY_ID = "default"


@pytest.fixture(scope="module")
def auth_session():
    """Create authenticated session for all tests"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Login
    resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return session


@pytest.fixture(scope="module")
def test_beo_id(auth_session):
    """Create a test BEO and return its ID for other tests"""
    unique_name = f"TEST_BEO_{uuid.uuid4().hex[:6]}"
    payload = {
        "property_id": PROPERTY_ID,
        "event_name": unique_name,
        "event_date": "2026-05-15",
        "start_time": "18:00",
        "end_time": "23:00",
        "venue_room": "Grand Ballroom",
        "guest_count": 150,
        "setup_style": "banquet",
        "status": "draft",
        "menu": [{"name": "Starter", "items": ["Soup", "Salad"], "notes": "Vegan option"}],
        "beverages": [{"name": "Wine", "qty": "Open bar", "notes": "Red and white"}],
        "av": [{"name": "Projector", "qty": 2, "notes": "4K"}],
        "contacts": [{"name": "John Doe", "role": "Client", "phone": "+1234567890", "email": "john@test.com"}],
        "decoration": "Floral centerpieces",
        "special_requests": "Wheelchair access",
        "billing_instructions": "Invoice to company",
        "notes": "VIP event"
    }
    resp = auth_session.post(f"{BASE_URL}/api/banquet-orders", json=payload)
    assert resp.status_code == 200, f"Failed to create test BEO: {resp.text}"
    data = resp.json()
    yield data["id"]
    
    # Cleanup
    auth_session.delete(f"{BASE_URL}/api/banquet-orders/{data['id']}")


class TestBeoList:
    """GET /api/banquet-orders/{property_id} - List BEOs"""
    
    def test_list_beos_success(self, auth_session):
        """List all BEOs for property"""
        resp = auth_session.get(f"{BASE_URL}/api/banquet-orders/{PROPERTY_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "count" in data
        assert isinstance(data["items"], list)
        print(f"Found {data['count']} BEOs")
    
    def test_list_beos_with_date_filter(self, auth_session):
        """List BEOs with date range filter"""
        resp = auth_session.get(f"{BASE_URL}/api/banquet-orders/{PROPERTY_ID}?from_date=2026-01-01&to_date=2026-12-31")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        print(f"Found {data['count']} BEOs in date range")
    
    def test_list_beos_with_status_filter(self, auth_session):
        """List BEOs with status filter"""
        resp = auth_session.get(f"{BASE_URL}/api/banquet-orders/{PROPERTY_ID}?status=draft")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        # All items should have draft status
        for item in data["items"]:
            assert item.get("status") == "draft"
        print(f"Found {data['count']} draft BEOs")
    
    def test_list_beos_invalid_status_returns_400(self, auth_session):
        """Invalid status query param should return 400"""
        resp = auth_session.get(f"{BASE_URL}/api/banquet-orders/{PROPERTY_ID}?status=invalid_status")
        assert resp.status_code == 400
        print("Correctly rejected invalid status filter")


class TestBeoCreate:
    """POST /api/banquet-orders - Create BEO"""
    
    def test_create_beo_success(self, auth_session):
        """Create BEO with all fields"""
        unique_name = f"TEST_Create_{uuid.uuid4().hex[:6]}"
        payload = {
            "property_id": PROPERTY_ID,
            "event_name": unique_name,
            "event_date": "2026-06-20",
            "start_time": "19:00",
            "end_time": "22:00",
            "venue_room": "Conference Room A",
            "guest_count": 50,
            "setup_style": "theatre",
            "status": "draft"
        }
        resp = auth_session.post(f"{BASE_URL}/api/banquet-orders", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        
        # Verify response structure
        assert "id" in data
        assert "ref" in data
        assert data["ref"].startswith("BEO-")
        assert data["event_name"] == unique_name
        assert data["venue_room"] == "Conference Room A"
        assert data["guest_count"] == 50
        assert data["setup_style"] == "theatre"
        assert data["status"] == "draft"
        assert "created_at" in data
        assert "created_by" in data
        print(f"Created BEO with ref: {data['ref']}")
        
        # Cleanup
        auth_session.delete(f"{BASE_URL}/api/banquet-orders/{data['id']}")
    
    def test_create_beo_invalid_status_returns_400(self, auth_session):
        """Invalid status should return 400"""
        payload = {
            "property_id": PROPERTY_ID,
            "event_name": "Invalid Status Test",
            "event_date": "2026-06-20",
            "start_time": "19:00",
            "end_time": "22:00",
            "venue_room": "Room B",
            "status": "invalid_status"
        }
        resp = auth_session.post(f"{BASE_URL}/api/banquet-orders", json=payload)
        assert resp.status_code == 400
        print("Correctly rejected invalid status")
    
    def test_create_beo_invalid_setup_style_returns_400(self, auth_session):
        """Invalid setup_style should return 400"""
        payload = {
            "property_id": PROPERTY_ID,
            "event_name": "Invalid Setup Test",
            "event_date": "2026-06-20",
            "start_time": "19:00",
            "end_time": "22:00",
            "venue_room": "Room C",
            "setup_style": "invalid_setup"
        }
        resp = auth_session.post(f"{BASE_URL}/api/banquet-orders", json=payload)
        assert resp.status_code == 400
        print("Correctly rejected invalid setup_style")


class TestBeoSingle:
    """GET /api/banquet-orders/single/{beo_id} - Get single BEO"""
    
    def test_get_single_beo_success(self, auth_session, test_beo_id):
        """Get single BEO by ID"""
        resp = auth_session.get(f"{BASE_URL}/api/banquet-orders/single/{test_beo_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == test_beo_id
        assert "event_name" in data
        assert "venue_room" in data
        print(f"Retrieved BEO: {data['event_name']}")
    
    def test_get_single_beo_not_found(self, auth_session):
        """Non-existent BEO should return 404"""
        fake_id = str(uuid.uuid4())
        resp = auth_session.get(f"{BASE_URL}/api/banquet-orders/single/{fake_id}")
        assert resp.status_code == 404
        print("Correctly returned 404 for missing BEO")


class TestBeoUpdate:
    """PUT /api/banquet-orders/{beo_id} - Update BEO"""
    
    def test_update_beo_success(self, auth_session, test_beo_id):
        """Update BEO fields"""
        # First get current state
        get_resp = auth_session.get(f"{BASE_URL}/api/banquet-orders/single/{test_beo_id}")
        original = get_resp.json()
        
        # Update with new values
        updated_payload = {
            "property_id": original["property_id"],
            "event_name": original["event_name"] + " UPDATED",
            "event_date": original["event_date"],
            "start_time": original["start_time"],
            "end_time": original["end_time"],
            "venue_room": original["venue_room"],
            "guest_count": 200,
            "setup_style": "classroom",
            "status": "confirmed"
        }
        resp = auth_session.put(f"{BASE_URL}/api/banquet-orders/{test_beo_id}", json=updated_payload)
        assert resp.status_code == 200
        data = resp.json()
        
        # Verify updates
        assert data["guest_count"] == 200
        assert data["setup_style"] == "classroom"
        assert data["status"] == "confirmed"
        assert "updated_at" in data
        assert "updated_by" in data
        print(f"Updated BEO: guest_count=200, setup=classroom, status=confirmed")
        
        # Verify persistence with GET
        verify_resp = auth_session.get(f"{BASE_URL}/api/banquet-orders/single/{test_beo_id}")
        verify_data = verify_resp.json()
        assert verify_data["guest_count"] == 200
        assert verify_data["status"] == "confirmed"
    
    def test_update_beo_not_found(self, auth_session):
        """Update non-existent BEO should return 404"""
        fake_id = str(uuid.uuid4())
        payload = {
            "property_id": PROPERTY_ID,
            "event_name": "Ghost Event",
            "event_date": "2026-06-20",
            "start_time": "19:00",
            "end_time": "22:00",
            "venue_room": "Room X"
        }
        resp = auth_session.put(f"{BASE_URL}/api/banquet-orders/{fake_id}", json=payload)
        assert resp.status_code == 404
        print("Correctly returned 404 for missing BEO update")


class TestBeoDelete:
    """DELETE /api/banquet-orders/{beo_id} - Delete BEO"""
    
    def test_delete_beo_success(self, auth_session):
        """Delete BEO and verify removal"""
        # Create a BEO to delete
        payload = {
            "property_id": PROPERTY_ID,
            "event_name": f"TEST_Delete_{uuid.uuid4().hex[:6]}",
            "event_date": "2026-07-01",
            "start_time": "10:00",
            "end_time": "12:00",
            "venue_room": "Meeting Room"
        }
        create_resp = auth_session.post(f"{BASE_URL}/api/banquet-orders", json=payload)
        assert create_resp.status_code == 200
        beo_id = create_resp.json()["id"]
        
        # Delete
        del_resp = auth_session.delete(f"{BASE_URL}/api/banquet-orders/{beo_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["deleted"] == beo_id
        print(f"Deleted BEO: {beo_id}")
        
        # Verify deletion with GET
        verify_resp = auth_session.get(f"{BASE_URL}/api/banquet-orders/single/{beo_id}")
        assert verify_resp.status_code == 404
        print("Verified BEO no longer exists")
    
    def test_delete_beo_not_found(self, auth_session):
        """Delete non-existent BEO should return 404"""
        fake_id = str(uuid.uuid4())
        resp = auth_session.delete(f"{BASE_URL}/api/banquet-orders/{fake_id}")
        assert resp.status_code == 404
        print("Correctly returned 404 for missing BEO delete")


class TestBeoPdf:
    """GET /api/banquet-orders/{beo_id}/pdf - Generate PDF"""
    
    def test_generate_pdf_success(self, auth_session, test_beo_id):
        """Generate PDF and verify response"""
        resp = auth_session.get(f"{BASE_URL}/api/banquet-orders/{test_beo_id}/pdf")
        assert resp.status_code == 200
        
        # Verify Content-Type
        assert resp.headers.get("Content-Type") == "application/pdf"
        
        # Verify Content-Disposition has filename
        content_disp = resp.headers.get("Content-Disposition", "")
        assert "attachment" in content_disp
        assert "filename=" in content_disp
        assert ".pdf" in content_disp
        
        # Verify PDF bytes start with %PDF-1.4
        pdf_bytes = resp.content
        assert len(pdf_bytes) > 100, "PDF too small"
        assert pdf_bytes[:8] == b"%PDF-1.4", f"Invalid PDF header: {pdf_bytes[:20]}"
        print(f"Generated PDF: {len(pdf_bytes)} bytes, header valid")
    
    def test_generate_pdf_not_found(self, auth_session):
        """PDF for non-existent BEO should return 404"""
        fake_id = str(uuid.uuid4())
        resp = auth_session.get(f"{BASE_URL}/api/banquet-orders/{fake_id}/pdf")
        assert resp.status_code == 404
        print("Correctly returned 404 for missing BEO PDF")


class TestBeoDashboard:
    """GET /api/banquet-orders/dashboard/{property_id} - Dashboard stats"""
    
    def test_dashboard_success(self, auth_session):
        """Get dashboard stats"""
        resp = auth_session.get(f"{BASE_URL}/api/banquet-orders/dashboard/{PROPERTY_ID}")
        assert resp.status_code == 200
        data = resp.json()
        
        # Verify response structure
        assert "total" in data
        assert "by_status" in data
        assert "upcoming_7d_count" in data
        assert "upcoming_7d_guests" in data
        assert "upcoming_7d" in data
        
        # Verify by_status has all valid statuses
        assert "draft" in data["by_status"]
        assert "confirmed" in data["by_status"]
        assert "completed" in data["by_status"]
        assert "cancelled" in data["by_status"]
        
        # Verify upcoming_7d is a list
        assert isinstance(data["upcoming_7d"], list)
        
        print(f"Dashboard: total={data['total']}, by_status={data['by_status']}, upcoming_7d_count={data['upcoming_7d_count']}")


class TestRegressionPanels:
    """Light regression tests for existing panels"""
    
    def test_loyalty_tier_endpoint(self, auth_session):
        """Verify loyalty-tier endpoint still works"""
        resp = auth_session.get(f"{BASE_URL}/api/loyalty-tier/config/{PROPERTY_ID}")
        assert resp.status_code == 200
        print("Loyalty tier endpoint OK")
    
    def test_pricing_explain_endpoint(self, auth_session):
        """Verify pricing-explain endpoint still works"""
        resp = auth_session.get(f"{BASE_URL}/api/pricing/explain/dashboard/{PROPERTY_ID}")
        assert resp.status_code == 200
        print("Pricing explain endpoint OK")
    
    def test_hk_turnover_endpoint(self, auth_session):
        """Verify hk-turnover endpoint still works"""
        resp = auth_session.get(f"{BASE_URL}/api/hk-turnover/{PROPERTY_ID}")
        assert resp.status_code == 200
        print("HK turnover endpoint OK")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
