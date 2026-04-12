"""
Iteration 54 - PDF Invoice Generation, Financial KPIs, Guest Profile Timeline
Tests for:
- GET /api/accounting/invoices/{invoice_id}/pdf — generates downloadable PDF invoice
- GET /api/dashboard/financial-kpis/{property_id} — returns RevPAR, ADR, occupancy, revenue, profit, NPS, AR outstanding
- GET /api/guests/timeline/{guest_email} — returns full activity timeline
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuth:
    """Authentication for testing"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get auth token for admin user"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, f"Expected 'token' in response, got: {data.keys()}"
        return data["token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Get auth headers"""
        return {"Authorization": f"Bearer {auth_token}"}


class TestFinancialKPIs(TestAuth):
    """Test GET /api/dashboard/financial-kpis/{property_id}"""
    
    def test_financial_kpis_returns_200(self, auth_headers):
        """Financial KPIs endpoint returns 200"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/financial-kpis/aldgate-flats",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_financial_kpis_structure(self, auth_headers):
        """Financial KPIs returns expected fields"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/financial-kpis/aldgate-flats",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check all required fields are present
        required_fields = [
            "month", "adr", "revpar", "occupancy", "month_revenue",
            "month_expenses", "month_profit", "nps_score", "nps_responses",
            "ar_outstanding", "total_rooms", "room_nights_sold", "month_bookings"
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        # Validate data types
        assert isinstance(data["adr"], (int, float))
        assert isinstance(data["revpar"], (int, float))
        assert isinstance(data["occupancy"], (int, float))
        assert isinstance(data["month_revenue"], (int, float))
        assert isinstance(data["month_profit"], (int, float))
        assert isinstance(data["nps_score"], (int, float))
        assert isinstance(data["ar_outstanding"], (int, float))
    
    def test_financial_kpis_all_properties(self, auth_headers):
        """Financial KPIs works with 'all' property_id"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/financial-kpis/all",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "revpar" in data
        assert "adr" in data
    
    def test_financial_kpis_requires_auth(self):
        """Financial KPIs requires authentication"""
        response = requests.get(f"{BASE_URL}/api/dashboard/financial-kpis/aldgate-flats")
        assert response.status_code == 401


class TestGuestTimeline(TestAuth):
    """Test GET /api/guests/timeline/{guest_email}"""
    
    def test_guest_timeline_returns_200(self, auth_headers):
        """Guest timeline endpoint returns 200"""
        response = requests.get(
            f"{BASE_URL}/api/guests/timeline/test@example.com",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_guest_timeline_structure(self, auth_headers):
        """Guest timeline returns expected structure"""
        response = requests.get(
            f"{BASE_URL}/api/guests/timeline/test@example.com",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check required fields
        assert "guest_email" in data
        assert "timeline" in data
        assert "counts" in data
        assert data["guest_email"] == "test@example.com"
        
        # Check counts structure
        counts = data["counts"]
        assert "bookings" in counts
        assert "conversations" in counts
        assert "surveys" in counts
        assert "reviews" in counts
        assert "payments" in counts
    
    def test_guest_timeline_items_structure(self, auth_headers):
        """Guest timeline items have correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/guests/timeline/test@example.com",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # If there are timeline items, check their structure
        if data["timeline"]:
            item = data["timeline"][0]
            required_item_fields = ["type", "date", "title", "subtitle", "detail", "icon", "color"]
            for field in required_item_fields:
                assert field in item, f"Timeline item missing field: {field}"
    
    def test_guest_timeline_requires_auth(self):
        """Guest timeline requires authentication"""
        response = requests.get(f"{BASE_URL}/api/guests/timeline/test@example.com")
        assert response.status_code == 401


class TestPDFInvoiceGeneration(TestAuth):
    """Test GET /api/accounting/invoices/{invoice_id}/pdf"""
    
    @pytest.fixture(scope="class")
    def test_invoice_id(self, auth_headers):
        """Create a test invoice and return its ID"""
        # First, create an invoice
        invoice_data = {
            "property_id": "aldgate-flats",
            "invoice_type": "receivable",
            "counterparty": "TEST_PDF_Guest",
            "due_date": "2026-02-15",
            "items": [
                {"description": "Room Charge", "quantity": 2, "unit_price": 150, "vat_rate": 20},
                {"description": "Breakfast", "quantity": 2, "unit_price": 25, "vat_rate": 20}
            ]
        }
        response = requests.post(
            f"{BASE_URL}/api/accounting/invoices",
            json=invoice_data,
            headers=auth_headers
        )
        assert response.status_code in [200, 201], f"Failed to create invoice: {response.text}"
        data = response.json()
        return data["id"]
    
    def test_pdf_generation_returns_pdf(self, auth_headers, test_invoice_id):
        """PDF endpoint returns application/pdf content type"""
        response = requests.get(
            f"{BASE_URL}/api/accounting/invoices/{test_invoice_id}/pdf",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        assert "application/pdf" in response.headers.get("Content-Type", ""), \
            f"Expected application/pdf, got {response.headers.get('Content-Type')}"
    
    def test_pdf_has_content_disposition(self, auth_headers, test_invoice_id):
        """PDF response has Content-Disposition header for download"""
        response = requests.get(
            f"{BASE_URL}/api/accounting/invoices/{test_invoice_id}/pdf",
            headers=auth_headers
        )
        assert response.status_code == 200
        content_disp = response.headers.get("Content-Disposition", "")
        assert "attachment" in content_disp, f"Expected attachment in Content-Disposition, got {content_disp}"
        assert ".pdf" in content_disp, f"Expected .pdf in filename, got {content_disp}"
    
    def test_pdf_has_content(self, auth_headers, test_invoice_id):
        """PDF response has actual content (not empty)"""
        response = requests.get(
            f"{BASE_URL}/api/accounting/invoices/{test_invoice_id}/pdf",
            headers=auth_headers
        )
        assert response.status_code == 200
        # PDF files start with %PDF
        assert response.content[:4] == b'%PDF', "Response does not appear to be a valid PDF"
        assert len(response.content) > 1000, "PDF content seems too small"
    
    def test_pdf_nonexistent_invoice_returns_404(self, auth_headers):
        """PDF endpoint returns 404 for non-existent invoice"""
        response = requests.get(
            f"{BASE_URL}/api/accounting/invoices/nonexistent-invoice-id/pdf",
            headers=auth_headers
        )
        assert response.status_code == 404
    
    def test_pdf_requires_auth(self, test_invoice_id):
        """PDF endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/accounting/invoices/{test_invoice_id}/pdf")
        assert response.status_code == 401


class TestExistingDashboardFeatures(TestAuth):
    """Regression tests for existing dashboard features"""
    
    def test_dashboard_overview_still_works(self, auth_headers):
        """Dashboard overview endpoint still works"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/overview/aldgate-flats",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "bookings" in data
        assert "messaging" in data
        assert "reviews" in data
    
    def test_dashboard_notifications_still_works(self, auth_headers):
        """Dashboard notifications endpoint still works"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/notifications/aldgate-flats",
            headers=auth_headers
        )
        assert response.status_code == 200
    
    def test_gss_still_works(self, auth_headers):
        """GSS endpoint still works"""
        response = requests.get(
            f"{BASE_URL}/api/gss/aldgate-flats?days=30",
            headers=auth_headers
        )
        assert response.status_code == 200


class TestExistingAccountingFeatures(TestAuth):
    """Regression tests for existing accounting features"""
    
    def test_invoices_list_still_works(self, auth_headers):
        """Invoices list endpoint still works"""
        response = requests.get(
            f"{BASE_URL}/api/accounting/invoices/aldgate-flats",
            headers=auth_headers
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    def test_pnl_still_works(self, auth_headers):
        """P&L endpoint still works"""
        response = requests.get(
            f"{BASE_URL}/api/accounting/pnl/aldgate-flats?period=2026-01",
            headers=auth_headers
        )
        assert response.status_code == 200
    
    def test_balance_sheet_still_works(self, auth_headers):
        """Balance sheet endpoint still works"""
        response = requests.get(
            f"{BASE_URL}/api/accounting/balance-sheet/aldgate-flats",
            headers=auth_headers
        )
        assert response.status_code == 200
    
    def test_ar_aging_still_works(self, auth_headers):
        """AR Aging endpoint still works"""
        response = requests.get(
            f"{BASE_URL}/api/accounting/ar-aging/aldgate-flats",
            headers=auth_headers
        )
        assert response.status_code == 200
    
    def test_payments_still_works(self, auth_headers):
        """Payments endpoint still works"""
        response = requests.get(
            f"{BASE_URL}/api/accounting/payments/aldgate-flats?month=2026-01",
            headers=auth_headers
        )
        assert response.status_code == 200
    
    def test_bank_recon_still_works(self, auth_headers):
        """Bank reconciliation summary still works"""
        response = requests.get(
            f"{BASE_URL}/api/accounting/bank-reconciliation/summary/aldgate-flats?month=2026-01",
            headers=auth_headers
        )
        assert response.status_code == 200


class TestCleanup(TestAuth):
    """Cleanup test data"""
    
    def test_cleanup_test_invoices(self, auth_headers):
        """Clean up TEST_ prefixed invoices"""
        # Get all invoices
        response = requests.get(
            f"{BASE_URL}/api/accounting/invoices/aldgate-flats",
            headers=auth_headers
        )
        if response.status_code == 200:
            invoices = response.json()
            for inv in invoices:
                if inv.get("counterparty", "").startswith("TEST_"):
                    # Delete test invoice
                    requests.delete(
                        f"{BASE_URL}/api/accounting/invoices/{inv['id']}",
                        headers=auth_headers
                    )
        assert True  # Cleanup is best-effort
