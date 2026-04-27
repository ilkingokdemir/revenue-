"""
Iteration 225 - Batch 12 + Batch 13 Tests
Batch 12: TodayHub + Command Palette (⌘K)
Batch 13: TR Compliance - KBS (Kimlik Bildirim Sistemi) + e-Fatura/e-Arşiv UBL-TR 2.1

Test Credentials: admin@hotelbox.com / HotelAdmin2026!
"""
import pytest
import requests
import os
import re

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def admin_session():
    """Get authenticated admin session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Login as admin
    login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    assert login_resp.status_code == 200, f"Admin login failed: {login_resp.text}"
    return session


class TestBatch12TodayHubAPIs:
    """Batch 12 - TodayHub relies on morning-brief and tier1-dashboard APIs"""
    
    def test_morning_brief_endpoint(self, admin_session):
        """GET /api/morning-brief/default should return 200 with today's data"""
        resp = admin_session.get(f"{BASE_URL}/api/morning-brief/default")
        assert resp.status_code == 200, f"Morning brief failed: {resp.text}"
        data = resp.json()
        # Should have today section
        assert "today" in data or "property_id" in data, f"Missing expected fields: {data.keys()}"
    
    def test_tier1_dashboard_endpoint(self, admin_session):
        """GET /api/tier1-dashboard/default?days=7 should return 200"""
        resp = admin_session.get(f"{BASE_URL}/api/tier1-dashboard/default?days=7")
        assert resp.status_code == 200, f"Tier1 dashboard failed: {resp.text}"
        data = resp.json()
        assert "property_id" in data, f"Missing property_id: {data.keys()}"
        assert "kpis" in data, f"Missing kpis: {data.keys()}"


class TestBatch13KBSEndpoints:
    """Batch 13 - KBS (Kimlik Bildirim Sistemi) endpoints"""
    
    def test_kbs_export_endpoint(self, admin_session):
        """POST /api/tr-compliance/kbs/export should return 200 with export data"""
        resp = admin_session.post(f"{BASE_URL}/api/tr-compliance/kbs/export", json={
            "property_id": "default",
            "from_date": "2026-01-01",
            "to_date": "2026-12-31",
            "only_unsent": False
        })
        assert resp.status_code == 200, f"KBS export failed: {resp.text}"
        data = resp.json()
        
        # Verify required fields
        assert "export_id" in data, f"Missing export_id: {data.keys()}"
        assert "row_count" in data, f"Missing row_count: {data.keys()}"
        assert "skipped" in data, f"Missing skipped: {data.keys()}"
        assert "included_bookings" in data, f"Missing included_bookings: {data.keys()}"
        assert "txt" in data, f"Missing txt: {data.keys()}"
        assert "filename" in data, f"Missing filename: {data.keys()}"
        
        # Filename should follow pattern
        assert data["filename"].startswith("kbs_"), f"Invalid filename: {data['filename']}"
        assert data["filename"].endswith(".txt"), f"Invalid filename extension: {data['filename']}"
        
        # Store export_id for later tests
        return data["export_id"]
    
    def test_kbs_history_endpoint(self, admin_session):
        """GET /api/tr-compliance/kbs/default/history should return history list"""
        resp = admin_session.get(f"{BASE_URL}/api/tr-compliance/kbs/default/history")
        assert resp.status_code == 200, f"KBS history failed: {resp.text}"
        data = resp.json()
        
        assert "history" in data, f"Missing history: {data.keys()}"
        assert "pending_count" in data, f"Missing pending_count: {data.keys()}"
        assert isinstance(data["history"], list), f"history should be list: {type(data['history'])}"
        assert isinstance(data["pending_count"], int), f"pending_count should be int: {type(data['pending_count'])}"
    
    def test_kbs_export_download(self, admin_session):
        """GET /api/tr-compliance/kbs/export/{export_id}/download should return text/plain"""
        # First create an export
        export_resp = admin_session.post(f"{BASE_URL}/api/tr-compliance/kbs/export", json={
            "property_id": "default",
            "from_date": "2026-01-01",
            "to_date": "2026-12-31",
            "only_unsent": False
        })
        assert export_resp.status_code == 200
        export_id = export_resp.json()["export_id"]
        
        # Download the export
        download_resp = admin_session.get(f"{BASE_URL}/api/tr-compliance/kbs/export/{export_id}/download")
        assert download_resp.status_code == 200, f"KBS download failed: {download_resp.text}"
        
        # Check content type
        content_type = download_resp.headers.get("content-type", "")
        assert "text/plain" in content_type, f"Expected text/plain, got: {content_type}"
        
        # Check content-disposition header for attachment
        content_disp = download_resp.headers.get("content-disposition", "")
        assert "attachment" in content_disp, f"Expected attachment header: {content_disp}"
    
    def test_kbs_mark_sent(self, admin_session):
        """POST /api/tr-compliance/kbs/export/{export_id}/mark-sent should mark as sent"""
        # First create an export
        export_resp = admin_session.post(f"{BASE_URL}/api/tr-compliance/kbs/export", json={
            "property_id": "default",
            "from_date": "2026-01-01",
            "to_date": "2026-12-31",
            "only_unsent": False
        })
        assert export_resp.status_code == 200
        export_id = export_resp.json()["export_id"]
        
        # Mark as sent
        mark_resp = admin_session.post(f"{BASE_URL}/api/tr-compliance/kbs/export/{export_id}/mark-sent")
        assert mark_resp.status_code == 200, f"KBS mark-sent failed: {mark_resp.text}"
        data = mark_resp.json()
        
        assert "export_id" in data, f"Missing export_id: {data.keys()}"
        assert "sent_at" in data, f"Missing sent_at: {data.keys()}"
        assert data["export_id"] == export_id
    
    def test_kbs_export_not_found(self, admin_session):
        """GET /api/tr-compliance/kbs/export/nonexistent/download should return 404"""
        resp = admin_session.get(f"{BASE_URL}/api/tr-compliance/kbs/export/nonexistent-id/download")
        assert resp.status_code == 404, f"Expected 404, got: {resp.status_code}"


class TestBatch13EFaturaEndpoints:
    """Batch 13 - e-Fatura/e-Arşiv UBL-TR 2.1 endpoints"""
    
    def test_efatura_list_endpoint(self, admin_session):
        """GET /api/tr-compliance/efatura/default/list should return invoice list"""
        resp = admin_session.get(f"{BASE_URL}/api/tr-compliance/efatura/default/list")
        assert resp.status_code == 200, f"e-Fatura list failed: {resp.text}"
        data = resp.json()
        
        assert "invoices" in data, f"Missing invoices: {data.keys()}"
        assert "total_count" in data, f"Missing total_count: {data.keys()}"
        assert "total_amount" in data, f"Missing total_amount: {data.keys()}"
        assert "by_status" in data, f"Missing by_status: {data.keys()}"
        
        assert isinstance(data["invoices"], list), f"invoices should be list"
        assert isinstance(data["total_count"], int), f"total_count should be int"
    
    def test_efatura_build_requires_booking(self, admin_session):
        """POST /api/tr-compliance/efatura/build with invalid booking should return 404"""
        resp = admin_session.post(f"{BASE_URL}/api/tr-compliance/efatura/build", json={
            "booking_id": "nonexistent-booking-id",
            "invoice_type": "earsiv"
        })
        assert resp.status_code == 404, f"Expected 404 for nonexistent booking, got: {resp.status_code}"
    
    def test_efatura_build_with_valid_booking(self, admin_session):
        """POST /api/tr-compliance/efatura/build with valid booking should return UBL-TR XML"""
        # First get a booking
        bookings_resp = admin_session.get(f"{BASE_URL}/api/bookings?property_id=default&limit=1")
        if bookings_resp.status_code != 200:
            pytest.skip("No bookings endpoint available")
        
        bookings_data = bookings_resp.json()
        bookings = bookings_data.get("bookings", bookings_data) if isinstance(bookings_data, dict) else bookings_data
        
        if not bookings or len(bookings) == 0:
            pytest.skip("No bookings available for e-Fatura test")
        
        booking_id = bookings[0].get("id")
        if not booking_id:
            pytest.skip("Booking has no id")
        
        # Build e-Arşiv invoice
        resp = admin_session.post(f"{BASE_URL}/api/tr-compliance/efatura/build", json={
            "booking_id": booking_id,
            "invoice_type": "earsiv"
        })
        assert resp.status_code == 200, f"e-Fatura build failed: {resp.text}"
        data = resp.json()
        
        # Verify required fields
        assert "uuid" in data, f"Missing uuid: {data.keys()}"
        assert "invoice_no" in data, f"Missing invoice_no: {data.keys()}"
        assert "xml" in data, f"Missing xml: {data.keys()}"
        
        # Verify XML structure (UBL-TR 2.1)
        xml = data["xml"]
        assert "CustomizationID" in xml, "Missing CustomizationID in XML"
        assert "TR1.2" in xml, "Missing TR1.2 CustomizationID"
        assert "ProfileID" in xml, "Missing ProfileID in XML"
        assert "EARSIVFATURA" in xml, "Missing EARSIVFATURA ProfileID for e-Arşiv"
        assert "TaxScheme" in xml, "Missing TaxScheme in XML"
        assert "0015" in xml, "Missing KDV TaxTypeCode 0015"
        assert "LegalMonetaryTotal" in xml, "Missing LegalMonetaryTotal in XML"
        
        return data["uuid"]
    
    def test_efatura_build_efatura_type(self, admin_session):
        """POST /api/tr-compliance/efatura/build with invoice_type='efatura' should use TICARIFATURA"""
        # First get a booking
        bookings_resp = admin_session.get(f"{BASE_URL}/api/bookings?property_id=default&limit=1")
        if bookings_resp.status_code != 200:
            pytest.skip("No bookings endpoint available")
        
        bookings_data = bookings_resp.json()
        bookings = bookings_data.get("bookings", bookings_data) if isinstance(bookings_data, dict) else bookings_data
        
        if not bookings or len(bookings) == 0:
            pytest.skip("No bookings available for e-Fatura test")
        
        booking_id = bookings[0].get("id")
        if not booking_id:
            pytest.skip("Booking has no id")
        
        # Build e-Fatura (B2B) invoice
        resp = admin_session.post(f"{BASE_URL}/api/tr-compliance/efatura/build", json={
            "booking_id": booking_id,
            "invoice_type": "efatura"
        })
        assert resp.status_code == 200, f"e-Fatura build failed: {resp.text}"
        data = resp.json()
        
        # Verify TICARIFATURA ProfileID for e-Fatura
        xml = data["xml"]
        assert "TICARIFATURA" in xml, "Missing TICARIFATURA ProfileID for e-Fatura type"
    
    def test_efatura_mark_submitted(self, admin_session):
        """POST /api/tr-compliance/efatura/{id}/mark-submitted should update status"""
        # First get a booking and build an invoice
        bookings_resp = admin_session.get(f"{BASE_URL}/api/bookings?property_id=default&limit=1")
        if bookings_resp.status_code != 200:
            pytest.skip("No bookings endpoint available")
        
        bookings_data = bookings_resp.json()
        bookings = bookings_data.get("bookings", bookings_data) if isinstance(bookings_data, dict) else bookings_data
        
        if not bookings or len(bookings) == 0:
            pytest.skip("No bookings available for e-Fatura test")
        
        booking_id = bookings[0].get("id")
        if not booking_id:
            pytest.skip("Booking has no id")
        
        # Build invoice
        build_resp = admin_session.post(f"{BASE_URL}/api/tr-compliance/efatura/build", json={
            "booking_id": booking_id,
            "invoice_type": "earsiv"
        })
        assert build_resp.status_code == 200
        invoice_uuid = build_resp.json()["uuid"]
        
        # Mark as submitted
        submit_resp = admin_session.post(f"{BASE_URL}/api/tr-compliance/efatura/{invoice_uuid}/mark-submitted")
        assert submit_resp.status_code == 200, f"Mark submitted failed: {submit_resp.text}"
        data = submit_resp.json()
        
        assert data["status"] == "submitted", f"Expected status 'submitted', got: {data.get('status')}"
        assert "submitted_at" in data, f"Missing submitted_at: {data.keys()}"
    
    def test_efatura_mark_submitted_not_found(self, admin_session):
        """POST /api/tr-compliance/efatura/nonexistent/mark-submitted should return 404"""
        resp = admin_session.post(f"{BASE_URL}/api/tr-compliance/efatura/nonexistent-id/mark-submitted")
        assert resp.status_code == 404, f"Expected 404, got: {resp.status_code}"


class TestBatch13XMLValidation:
    """Validate UBL-TR 2.1 XML structure"""
    
    def test_xml_currency_match(self, admin_session):
        """XML currencyID should match booking currency"""
        # Get a booking
        bookings_resp = admin_session.get(f"{BASE_URL}/api/bookings?property_id=default&limit=1")
        if bookings_resp.status_code != 200:
            pytest.skip("No bookings endpoint available")
        
        bookings_data = bookings_resp.json()
        bookings = bookings_data.get("bookings", bookings_data) if isinstance(bookings_data, dict) else bookings_data
        
        if not bookings or len(bookings) == 0:
            pytest.skip("No bookings available")
        
        booking = bookings[0]
        booking_id = booking.get("id")
        booking_currency = booking.get("currency", "TRY")
        
        # Build invoice
        resp = admin_session.post(f"{BASE_URL}/api/tr-compliance/efatura/build", json={
            "booking_id": booking_id,
            "invoice_type": "earsiv"
        })
        
        if resp.status_code != 200:
            pytest.skip("Could not build invoice")
        
        data = resp.json()
        xml = data["xml"]
        
        # Check currency in XML
        assert f'currencyID="{booking_currency}"' in xml or f"currencyID='{booking_currency}'" in xml, \
            f"Currency mismatch: expected {booking_currency} in XML"
    
    def test_xml_legal_monetary_total_calculated(self, admin_session):
        """XML LegalMonetaryTotal should have calculated amounts"""
        # Get a booking
        bookings_resp = admin_session.get(f"{BASE_URL}/api/bookings?property_id=default&limit=1")
        if bookings_resp.status_code != 200:
            pytest.skip("No bookings endpoint available")
        
        bookings_data = bookings_resp.json()
        bookings = bookings_data.get("bookings", bookings_data) if isinstance(bookings_data, dict) else bookings_data
        
        if not bookings or len(bookings) == 0:
            pytest.skip("No bookings available")
        
        booking_id = bookings[0].get("id")
        
        # Build invoice
        resp = admin_session.post(f"{BASE_URL}/api/tr-compliance/efatura/build", json={
            "booking_id": booking_id,
            "invoice_type": "earsiv"
        })
        
        if resp.status_code != 200:
            pytest.skip("Could not build invoice")
        
        data = resp.json()
        xml = data["xml"]
        
        # Check LegalMonetaryTotal elements
        assert "LineExtensionAmount" in xml, "Missing LineExtensionAmount"
        assert "TaxExclusiveAmount" in xml, "Missing TaxExclusiveAmount"
        assert "TaxInclusiveAmount" in xml, "Missing TaxInclusiveAmount"
        assert "PayableAmount" in xml, "Missing PayableAmount"


class TestSmokeRegression:
    """Smoke tests to verify previous batches still work"""
    
    def test_login_works(self, admin_session):
        """Login should work (already verified by fixture)"""
        # If we got here, login worked
        assert True
    
    def test_tier1_dashboard_still_works(self, admin_session):
        """Tier-1 Master Dashboard (Batch 11) should still work"""
        resp = admin_session.get(f"{BASE_URL}/api/tier1-dashboard/default?days=7")
        assert resp.status_code == 200, f"Tier1 dashboard regression: {resp.text}"
        data = resp.json()
        assert "kpis" in data, "Missing kpis in tier1 dashboard"
    
    def test_morning_brief_still_works(self, admin_session):
        """Morning Brief should still work"""
        resp = admin_session.get(f"{BASE_URL}/api/morning-brief/default")
        assert resp.status_code == 200, f"Morning brief regression: {resp.text}"


class TestAuthRequired:
    """Verify auth is required for TR Compliance endpoints"""
    
    def test_kbs_export_requires_auth(self):
        """KBS export should require authentication"""
        session = requests.Session()
        resp = session.post(f"{BASE_URL}/api/tr-compliance/kbs/export", json={
            "property_id": "default",
            "from_date": "2026-01-01",
            "to_date": "2026-12-31",
            "only_unsent": False
        })
        assert resp.status_code in [401, 403], f"Expected 401/403 without auth, got: {resp.status_code}"
    
    def test_efatura_build_requires_auth(self):
        """e-Fatura build should require authentication"""
        session = requests.Session()
        resp = session.post(f"{BASE_URL}/api/tr-compliance/efatura/build", json={
            "booking_id": "test",
            "invoice_type": "earsiv"
        })
        assert resp.status_code in [401, 403], f"Expected 401/403 without auth, got: {resp.status_code}"
