"""
Iteration 123 - PMS Features: Digital Check-in, Invoice/Folio Management, Scheduled Reports
Tests for:
1. Digital Check-in / Registration Card (public + auth endpoints)
2. Invoice/Folio Management (charges, payments, adjustments)
3. Scheduled Reports (CRUD + preview)
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for admin user"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    if response.status_code == 200:
        return response.cookies.get('access_token') or response.json().get('access_token')
    pytest.skip("Authentication failed - skipping authenticated tests")

@pytest.fixture(scope="module")
def auth_session(auth_token):
    """Session with auth cookies"""
    session = requests.Session()
    session.cookies.set('access_token', auth_token)
    session.headers.update({"Content-Type": "application/json"})
    return session

@pytest.fixture(scope="module")
def booking_id(auth_session):
    """Get a valid booking ID from timeline"""
    response = auth_session.get(f"{BASE_URL}/api/bookings/timeline/all?days=30")
    if response.status_code == 200:
        data = response.json()
        groups = data.get('groups', [])
        for group in groups:
            rooms = group.get('rooms', [])
            for room in rooms:
                bookings = room.get('bookings', [])
                if bookings:
                    return bookings[0]['id']
    pytest.skip("No bookings found for testing")

@pytest.fixture(scope="module")
def property_id(auth_session):
    """Get a valid property ID"""
    response = auth_session.get(f"{BASE_URL}/api/properties")
    if response.status_code == 200:
        props = response.json()
        if props:
            return props[0]['id']
    return "all"


# ===========================
# 1. DIGITAL CHECK-IN TESTS
# ===========================

class TestDigitalCheckin:
    """Digital Check-in / Registration Card tests"""
    
    def test_get_checkin_form_public(self, booking_id):
        """GET /api/guest-checkin/{booking_id} - Public endpoint (no auth)"""
        response = requests.get(f"{BASE_URL}/api/guest-checkin/{booking_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "booking" in data, "Response should contain booking info"
        assert "property" in data, "Response should contain property info"
        assert "registration" in data, "Response should contain registration status"
        assert "completed" in data, "Response should contain completed flag"
        
        # Verify booking structure
        booking = data["booking"]
        assert "id" in booking
        assert "guest_name" in booking
        assert "check_in" in booking
        assert "check_out" in booking
        print(f"✓ GET /api/guest-checkin/{booking_id[:8]}... - Public endpoint returns booking info")
    
    def test_get_checkin_form_not_found(self):
        """GET /api/guest-checkin/{invalid_id} - Returns 404"""
        fake_id = str(uuid.uuid4())
        response = requests.get(f"{BASE_URL}/api/guest-checkin/{fake_id}")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ GET /api/guest-checkin/{invalid_id} - Returns 404 for non-existent booking")
    
    def test_submit_checkin_form_public(self, booking_id):
        """POST /api/guest-checkin/{booking_id} - Public endpoint submits registration"""
        registration_data = {
            "guest_name": "TEST_John Smith",
            "email": "test_john@example.com",
            "phone": "+44 7700 900123",
            "nationality": "British",
            "passport_number": "TEST123456",
            "id_type": "passport",
            "id_number": "TEST123456",
            "date_of_birth": "1985-06-15",
            "address": "123 Test Street",
            "city": "London",
            "country": "United Kingdom",
            "postcode": "SW1A 1AA",
            "emergency_contact_name": "Jane Smith",
            "emergency_contact_phone": "+44 7700 900456",
            "special_requests": "Late checkout if possible",
            "arrival_time": "15:00",
            "vehicle_reg": "AB12 CDE",
            "signature": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            "terms_accepted": True,
            "marketing_consent": False
        }
        
        response = requests.post(f"{BASE_URL}/api/guest-checkin/{booking_id}", json=registration_data)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("status") == "completed", "Registration should be completed"
        assert "registration_id" in data, "Should return registration_id"
        print(f"✓ POST /api/guest-checkin/{booking_id[:8]}... - Registration submitted successfully")
    
    def test_send_checkin_link_requires_auth(self, booking_id):
        """POST /api/guest-checkin/send-link/{booking_id} - Requires authentication"""
        response = requests.post(f"{BASE_URL}/api/guest-checkin/send-link/{booking_id}")
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"
        print("✓ POST /api/guest-checkin/send-link - Requires authentication")
    
    def test_send_checkin_link_with_auth(self, auth_session, booking_id):
        """POST /api/guest-checkin/send-link/{booking_id} - Sends check-in link notification"""
        response = auth_session.post(f"{BASE_URL}/api/guest-checkin/send-link/{booking_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("status") == "sent", "Status should be 'sent'"
        assert "link" in data, "Should return check-in link"
        assert f"/checkin/{booking_id}" in data["link"], "Link should contain booking ID"
        print(f"✓ POST /api/guest-checkin/send-link/{booking_id[:8]}... - Check-in link sent")


# ===========================
# 2. FOLIO MANAGEMENT TESTS
# ===========================

class TestFolioManagement:
    """Invoice/Folio Management tests"""
    
    def test_get_folio_requires_auth(self, booking_id):
        """GET /api/folio/{booking_id} - Requires authentication"""
        response = requests.get(f"{BASE_URL}/api/folio/{booking_id}")
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"
        print("✓ GET /api/folio - Requires authentication")
    
    def test_get_folio_with_auth(self, auth_session, booking_id):
        """GET /api/folio/{booking_id} - Returns full folio with invoice details"""
        response = auth_session.get(f"{BASE_URL}/api/folio/{booking_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify folio structure
        assert "invoice_number" in data, "Should have invoice_number"
        assert data["invoice_number"].startswith("INV-"), "Invoice number should start with INV-"
        assert "booking" in data, "Should have booking info"
        assert "property" in data, "Should have property info"
        assert "room" in data, "Should have room info"
        assert "items" in data, "Should have items list"
        assert "totals" in data, "Should have totals"
        assert "currency" in data, "Should have currency"
        
        # Verify totals structure
        totals = data["totals"]
        assert "charges" in totals, "Totals should have charges"
        assert "payments" in totals, "Totals should have payments"
        assert "adjustments" in totals, "Totals should have adjustments"
        assert "balance_due" in totals, "Totals should have balance_due"
        
        print(f"✓ GET /api/folio/{booking_id[:8]}... - Returns invoice {data['invoice_number']}")
        print(f"  Charges: £{totals['charges']}, Payments: £{totals['payments']}, Balance: £{totals['balance_due']}")
    
    def test_add_charge_requires_auth(self, booking_id):
        """POST /api/folio/{booking_id}/add-charge - Requires authentication"""
        response = requests.post(f"{BASE_URL}/api/folio/{booking_id}/add-charge", json={
            "description": "Test charge",
            "unit_price": 10.00,
            "category": "minibar"
        })
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"
        print("✓ POST /api/folio/add-charge - Requires authentication")
    
    def test_add_charge_with_auth(self, auth_session, booking_id):
        """POST /api/folio/{booking_id}/add-charge - Adds charge to folio"""
        charge_data = {
            "description": "TEST_Minibar - Wine",
            "unit_price": 15.50,
            "quantity": 2,
            "category": "minibar"
        }
        
        response = auth_session.post(f"{BASE_URL}/api/folio/{booking_id}/add-charge", json=charge_data)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("type") == "charge", "Item type should be 'charge'"
        assert data.get("category") == "minibar", "Category should be 'minibar'"
        assert data.get("amount") == 31.00, f"Amount should be 31.00 (15.50 x 2), got {data.get('amount')}"
        assert "id" in data, "Should return item ID"
        print(f"✓ POST /api/folio/{booking_id[:8]}... /add-charge - Added £{data['amount']} charge")
    
    def test_add_payment_requires_auth(self, booking_id):
        """POST /api/folio/{booking_id}/add-payment - Requires authentication"""
        response = requests.post(f"{BASE_URL}/api/folio/{booking_id}/add-payment", json={
            "amount": 100.00,
            "method": "card"
        })
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"
        print("✓ POST /api/folio/add-payment - Requires authentication")
    
    def test_add_payment_with_auth(self, auth_session, booking_id):
        """POST /api/folio/{booking_id}/add-payment - Records payment and updates status"""
        payment_data = {
            "amount": 50.00,
            "method": "card",
            "description": "TEST_Partial payment",
            "reference": "TXN-TEST-123"
        }
        
        response = auth_session.post(f"{BASE_URL}/api/folio/{booking_id}/add-payment", json=payment_data)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("type") == "payment", "Item type should be 'payment'"
        assert data.get("amount") == 50.00, f"Amount should be 50.00, got {data.get('amount')}"
        assert "id" in data, "Should return item ID"
        print(f"✓ POST /api/folio/{booking_id[:8]}... /add-payment - Recorded £{data['amount']} payment")
    
    def test_add_adjustment_requires_auth(self, booking_id):
        """POST /api/folio/{booking_id}/adjust - Requires authentication (admin/manager)"""
        response = requests.post(f"{BASE_URL}/api/folio/{booking_id}/adjust", json={
            "amount": -10.00,
            "reason": "discount"
        })
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"
        print("✓ POST /api/folio/adjust - Requires authentication")
    
    def test_add_adjustment_with_auth(self, auth_session, booking_id):
        """POST /api/folio/{booking_id}/adjust - Adds adjustment (discount/refund)"""
        adjustment_data = {
            "amount": -10.00,
            "reason": "discount",
            "description": "TEST_Loyalty discount"
        }
        
        response = auth_session.post(f"{BASE_URL}/api/folio/{booking_id}/adjust", json=adjustment_data)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("type") == "adjustment", "Item type should be 'adjustment'"
        assert data.get("category") == "discount", "Category should be 'discount'"
        assert "id" in data, "Should return item ID"
        print(f"✓ POST /api/folio/{booking_id[:8]}... /adjust - Added £{data['amount']} adjustment")
    
    def test_folio_totals_updated(self, auth_session, booking_id):
        """GET /api/folio/{booking_id} - Verify totals include new items"""
        response = auth_session.get(f"{BASE_URL}/api/folio/{booking_id}")
        assert response.status_code == 200
        
        data = response.json()
        items = data.get("items", [])
        totals = data.get("totals", {})
        
        # Verify we have multiple item types
        item_types = set(item.get("type") for item in items)
        assert "charge" in item_types, "Should have charge items"
        
        # Verify totals are calculated
        assert totals.get("charges", 0) > 0, "Should have charges total"
        print(f"✓ Folio totals verified - {len(items)} items, Balance: £{totals.get('balance_due', 0)}")


# ===========================
# 3. SCHEDULED REPORTS TESTS
# ===========================

class TestScheduledReports:
    """Scheduled Reports tests"""
    
    def test_get_scheduled_reports_requires_auth(self, property_id):
        """GET /api/scheduled-reports/{property_id} - Requires authentication"""
        response = requests.get(f"{BASE_URL}/api/scheduled-reports/{property_id}")
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"
        print("✓ GET /api/scheduled-reports - Requires authentication")
    
    def test_get_scheduled_reports_with_auth(self, auth_session, property_id):
        """GET /api/scheduled-reports/{property_id} - Lists scheduled reports"""
        response = auth_session.get(f"{BASE_URL}/api/scheduled-reports/{property_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "reports" in data, "Response should contain reports list"
        print(f"✓ GET /api/scheduled-reports/{property_id[:8] if property_id != 'all' else 'all'}... - Found {len(data['reports'])} reports")
    
    def test_create_scheduled_report_requires_auth(self, property_id):
        """POST /api/scheduled-reports/{property_id} - Requires authentication"""
        response = requests.post(f"{BASE_URL}/api/scheduled-reports/{property_id}", json={
            "name": "Test Report",
            "frequency": "daily"
        })
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"
        print("✓ POST /api/scheduled-reports - Requires authentication")
    
    def test_create_scheduled_report_with_auth(self, auth_session, property_id):
        """POST /api/scheduled-reports/{property_id} - Creates new scheduled report"""
        report_data = {
            "name": "TEST_Daily Operations Report",
            "type": "daily_summary",
            "frequency": "daily",
            "time": "08:00",
            "recipients": ["manager@hotel.com", "gm@hotel.com"],
            "sections": ["occupancy", "revenue", "arrivals", "departures", "housekeeping"],
            "enabled": True,
            "format": "pdf"
        }
        
        response = auth_session.post(f"{BASE_URL}/api/scheduled-reports/{property_id}", json=report_data)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "id" in data, "Should return report ID"
        assert data.get("name") == "TEST_Daily Operations Report", "Name should match"
        assert data.get("frequency") == "daily", "Frequency should be daily"
        assert data.get("enabled") == True, "Should be enabled"
        assert len(data.get("sections", [])) == 5, "Should have 5 sections"
        
        # Store report ID for cleanup
        TestScheduledReports.created_report_id = data["id"]
        print(f"✓ POST /api/scheduled-reports - Created report '{data['name']}' (ID: {data['id'][:8]}...)")
    
    def test_preview_report_requires_auth(self, property_id):
        """POST /api/scheduled-reports/{property_id}/preview - Requires authentication"""
        response = requests.post(f"{BASE_URL}/api/scheduled-reports/{property_id}/preview")
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"
        print("✓ POST /api/scheduled-reports/preview - Requires authentication")
    
    def test_preview_report_with_auth(self, auth_session, property_id):
        """POST /api/scheduled-reports/{property_id}/preview - Generates report preview"""
        preview_data = {
            "type": "daily_summary",
            "sections": ["occupancy", "revenue", "arrivals", "departures", "housekeeping"]
        }
        
        response = auth_session.post(f"{BASE_URL}/api/scheduled-reports/{property_id}/preview", json=preview_data)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "report_type" in data, "Should have report_type"
        assert "property" in data, "Should have property name"
        assert "generated_at" in data, "Should have generated_at timestamp"
        assert "date" in data, "Should have date"
        assert "sections" in data, "Should have sections"
        
        sections = data.get("sections", {})
        # Verify section data
        if "occupancy" in sections:
            occ = sections["occupancy"]
            assert "total_rooms" in occ, "Occupancy should have total_rooms"
            assert "booked" in occ, "Occupancy should have booked count"
            assert "occupancy_pct" in occ, "Occupancy should have occupancy_pct"
            print(f"  Occupancy: {occ['occupancy_pct']}% ({occ['booked']}/{occ['total_rooms']} rooms)")
        
        if "revenue" in sections:
            rev = sections["revenue"]
            assert "todays_revenue" in rev, "Revenue should have todays_revenue"
            assert "avg_daily_rate" in rev, "Revenue should have avg_daily_rate"
            print(f"  Revenue: £{rev['todays_revenue']} (ADR: £{rev['avg_daily_rate']})")
        
        if "arrivals" in sections:
            arr = sections["arrivals"]
            assert "count" in arr, "Arrivals should have count"
            print(f"  Arrivals: {arr['count']} guests")
        
        if "departures" in sections:
            dep = sections["departures"]
            assert "count" in dep, "Departures should have count"
            print(f"  Departures: {dep['count']} guests")
        
        if "housekeeping" in sections:
            hk = sections["housekeeping"]
            assert "clean" in hk, "Housekeeping should have clean count"
            assert "dirty" in hk, "Housekeeping should have dirty count"
            print(f"  Housekeeping: {hk['clean']} clean, {hk['dirty']} dirty")
        
        print(f"✓ POST /api/scheduled-reports/preview - Generated {data['report_type']} report")
    
    def test_delete_scheduled_report_requires_auth(self, property_id):
        """DELETE /api/scheduled-reports/{property_id}/{report_id} - Requires authentication"""
        fake_id = str(uuid.uuid4())
        response = requests.delete(f"{BASE_URL}/api/scheduled-reports/{property_id}/{fake_id}")
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"
        print("✓ DELETE /api/scheduled-reports - Requires authentication")
    
    def test_delete_scheduled_report_with_auth(self, auth_session, property_id):
        """DELETE /api/scheduled-reports/{property_id}/{report_id} - Deletes report"""
        report_id = getattr(TestScheduledReports, 'created_report_id', None)
        if not report_id:
            pytest.skip("No report created to delete")
        
        response = auth_session.delete(f"{BASE_URL}/api/scheduled-reports/{property_id}/{report_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("status") == "deleted", "Status should be 'deleted'"
        print(f"✓ DELETE /api/scheduled-reports/{report_id[:8]}... - Report deleted")


# ===========================
# CLEANUP
# ===========================

class TestCleanup:
    """Cleanup test data"""
    
    def test_cleanup_test_folio_items(self, auth_session, booking_id):
        """Cleanup: Remove TEST_ prefixed folio items"""
        # Get folio to find test items
        response = auth_session.get(f"{BASE_URL}/api/folio/{booking_id}")
        if response.status_code == 200:
            data = response.json()
            test_items = [item for item in data.get("items", []) 
                         if item.get("description", "").startswith("TEST_")]
            print(f"✓ Cleanup: Found {len(test_items)} test folio items (manual cleanup may be needed)")
        else:
            print("✓ Cleanup: Could not retrieve folio for cleanup")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
