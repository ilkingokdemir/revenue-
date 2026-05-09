"""
Iteration 271: Turkish Bordro PDF Generation Tests
Tests for monthly payroll PDF generation compliant with 4857/5510 sayılı kanun.
Endpoints tested:
- GET /api/payroll/preview/{property_id}?month=YYYY-MM (JSON preview)
- GET /api/payroll/export-pdf/{property_id}?month=YYYY-MM (PDF download)
- GET /api/payroll/export/{property_id} (CSV - regression)
"""
import pytest
import requests
import os
import math

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Turkish payroll deduction rates (employee side)
TR_SGK_RATE = 0.14         # SGK İşçi Payı
TR_UNEMP_RATE = 0.01       # İşsizlik Sigortası İşçi Payı
TR_INCOME_TAX_RATE = 0.15  # Gelir Vergisi (1. dilim)
TR_STAMP_RATE = 0.00759    # Damga Vergisi


@pytest.fixture(scope="module")
def admin_token():
    """Get admin auth token"""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    if resp.status_code == 200:
        return resp.json().get("token")
    pytest.skip("Admin login failed - cannot proceed with tests")


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    """Auth headers for admin"""
    return {"Authorization": f"Bearer {admin_token}"}


class TestPayrollPreviewEndpoint:
    """Tests for GET /api/payroll/preview/{property_id}"""
    
    def test_preview_returns_200_with_data(self, auth_headers):
        """Preview endpoint returns 200 with valid month and property_id='all'"""
        resp = requests.get(
            f"{BASE_URL}/api/payroll/preview/all?month=2026-05",
            headers=auth_headers
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        # Verify response structure
        assert "property_id" in data
        assert "period" in data
        assert "month" in data
        assert "rows" in data
        assert "totals" in data
        assert "deduction_rates" in data
        
        # Verify deduction rates are present
        rates = data["deduction_rates"]
        assert "sgk" in rates
        assert "issizlik" in rates
        assert "gelir_vergisi" in rates
        assert "damga_vergisi" in rates
    
    def test_preview_rows_have_tr_deduction_fields(self, auth_headers):
        """Each row has brut/sgk/issizlik/gelir_vergisi/damga_vergisi/net fields"""
        resp = requests.get(
            f"{BASE_URL}/api/payroll/preview/all?month=2026-05",
            headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        
        if len(data["rows"]) > 0:
            row = data["rows"][0]
            required_fields = ["brut", "sgk", "issizlik", "gelir_vergisi", "damga_vergisi", "net"]
            for field in required_fields:
                assert field in row, f"Missing field: {field}"
    
    def test_preview_deduction_math_correct(self, auth_headers):
        """Verify net = brut - sgk - issizlik - gelir_vergisi - damga_vergisi (within 1 cent)"""
        resp = requests.get(
            f"{BASE_URL}/api/payroll/preview/all?month=2026-05",
            headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        
        for row in data["rows"]:
            brut = row["brut"]
            sgk = row["sgk"]
            issizlik = row["issizlik"]
            gelir_vergisi = row["gelir_vergisi"]
            damga_vergisi = row["damga_vergisi"]
            net = row["net"]
            
            expected_net = brut - sgk - issizlik - gelir_vergisi - damga_vergisi
            diff = abs(net - expected_net)
            assert diff <= 0.01, f"Net calculation off by {diff} for {row.get('staff_name')}: expected {expected_net}, got {net}"
    
    def test_preview_totals_sum_correctly(self, auth_headers):
        """Verify totals match sum of individual rows"""
        resp = requests.get(
            f"{BASE_URL}/api/payroll/preview/all?month=2026-05",
            headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        
        rows = data["rows"]
        totals = data["totals"]
        
        if len(rows) > 0:
            # Sum up rows
            sum_brut = sum(r["brut"] for r in rows)
            sum_net = sum(r["net"] for r in rows)
            
            assert abs(totals["brut"] - sum_brut) <= 0.01, f"Brut total mismatch: {totals['brut']} vs {sum_brut}"
            assert abs(totals["net"] - sum_net) <= 0.01, f"Net total mismatch: {totals['net']} vs {sum_net}"
    
    def test_preview_custom_rates_override(self, auth_headers):
        """Custom rates via query params are reflected in result"""
        custom_sgk = 0.20  # Override SGK to 20%
        resp = requests.get(
            f"{BASE_URL}/api/payroll/preview/all?month=2026-05&sgk={custom_sgk}",
            headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        
        # Verify the custom rate is reflected
        assert data["deduction_rates"]["sgk"] == custom_sgk
        
        # Verify SGK deduction uses custom rate
        for row in data["rows"]:
            if row["brut"] > 0:
                expected_sgk = round(row["brut"] * custom_sgk, 2)
                assert abs(row["sgk"] - expected_sgk) <= 0.01, f"SGK with custom rate mismatch: expected {expected_sgk}, got {row['sgk']}"
    
    def test_preview_requires_auth(self):
        """Preview endpoint requires authentication"""
        resp = requests.get(f"{BASE_URL}/api/payroll/preview/all?month=2026-05")
        assert resp.status_code in [401, 403], f"Expected 401/403 without auth, got {resp.status_code}"


class TestPayrollPDFEndpoint:
    """Tests for GET /api/payroll/export-pdf/{property_id}"""
    
    def test_pdf_returns_200_with_valid_data(self, auth_headers):
        """PDF endpoint returns 200 with valid month and data"""
        resp = requests.get(
            f"{BASE_URL}/api/payroll/export-pdf/all?month=2026-05",
            headers=auth_headers
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    
    def test_pdf_content_type_is_pdf(self, auth_headers):
        """Response Content-Type is application/pdf"""
        resp = requests.get(
            f"{BASE_URL}/api/payroll/export-pdf/all?month=2026-05",
            headers=auth_headers
        )
        assert resp.status_code == 200
        content_type = resp.headers.get("Content-Type", "")
        assert "application/pdf" in content_type, f"Expected application/pdf, got {content_type}"
    
    def test_pdf_starts_with_magic_header(self, auth_headers):
        """PDF content starts with %PDF- magic header"""
        resp = requests.get(
            f"{BASE_URL}/api/payroll/export-pdf/all?month=2026-05",
            headers=auth_headers
        )
        assert resp.status_code == 200
        content = resp.content
        assert content.startswith(b"%PDF-"), f"PDF does not start with %PDF- magic header"
    
    def test_pdf_has_content_disposition_attachment(self, auth_headers):
        """Response has Content-Disposition attachment with filename"""
        resp = requests.get(
            f"{BASE_URL}/api/payroll/export-pdf/all?month=2026-05",
            headers=auth_headers
        )
        assert resp.status_code == 200
        content_disp = resp.headers.get("Content-Disposition", "")
        assert "attachment" in content_disp, f"Expected attachment in Content-Disposition, got {content_disp}"
        assert "filename=" in content_disp, f"Expected filename in Content-Disposition, got {content_disp}"
        assert ".pdf" in content_disp, f"Expected .pdf in filename, got {content_disp}"
    
    def test_pdf_returns_404_when_no_shifts(self, auth_headers):
        """PDF returns 404 with detail when no completed shifts in period"""
        # Use a month with no data
        resp = requests.get(
            f"{BASE_URL}/api/payroll/export-pdf/all?month=1999-01",
            headers=auth_headers
        )
        assert resp.status_code == 404, f"Expected 404 for empty period, got {resp.status_code}"
        data = resp.json()
        assert "detail" in data, "Expected 'detail' in 404 response"
    
    def test_pdf_requires_auth(self):
        """PDF endpoint requires authentication"""
        resp = requests.get(f"{BASE_URL}/api/payroll/export-pdf/all?month=2026-05")
        assert resp.status_code in [401, 403], f"Expected 401/403 without auth, got {resp.status_code}"
    
    def test_pdf_has_reasonable_size(self, auth_headers):
        """PDF has reasonable file size (not empty, not too large)"""
        resp = requests.get(
            f"{BASE_URL}/api/payroll/export-pdf/all?month=2026-05",
            headers=auth_headers
        )
        assert resp.status_code == 200
        content_length = len(resp.content)
        assert content_length > 1000, f"PDF too small ({content_length} bytes), might be empty"
        assert content_length < 1000000, f"PDF too large ({content_length} bytes)"


class TestPayrollCSVRegression:
    """Regression tests for existing CSV endpoint"""
    
    def test_csv_export_still_works(self, auth_headers):
        """Existing CSV endpoint /api/payroll/export still works"""
        resp = requests.get(
            f"{BASE_URL}/api/payroll/export/all?month=2026-05",
            headers=auth_headers
        )
        assert resp.status_code == 200, f"CSV export failed: {resp.status_code}"
    
    def test_csv_content_type_is_csv(self, auth_headers):
        """CSV response has correct Content-Type"""
        resp = requests.get(
            f"{BASE_URL}/api/payroll/export/all?month=2026-05",
            headers=auth_headers
        )
        assert resp.status_code == 200
        content_type = resp.headers.get("Content-Type", "")
        assert "text/csv" in content_type, f"Expected text/csv, got {content_type}"
    
    def test_csv_has_content_disposition(self, auth_headers):
        """CSV has Content-Disposition attachment"""
        resp = requests.get(
            f"{BASE_URL}/api/payroll/export/all?month=2026-05",
            headers=auth_headers
        )
        assert resp.status_code == 200
        content_disp = resp.headers.get("Content-Disposition", "")
        assert "attachment" in content_disp
        assert ".csv" in content_disp
    
    def test_csv_requires_auth(self):
        """CSV endpoint requires authentication"""
        resp = requests.get(f"{BASE_URL}/api/payroll/export/all?month=2026-05")
        assert resp.status_code in [401, 403], f"Expected 401/403 without auth, got {resp.status_code}"


class TestTRPayrollDeductionMath:
    """Verify Turkish Labor Law deduction calculations"""
    
    def test_sgk_rate_14_percent(self, auth_headers):
        """SGK deduction is 14% of gross"""
        resp = requests.get(
            f"{BASE_URL}/api/payroll/preview/all?month=2026-05",
            headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        
        for row in data["rows"]:
            if row["brut"] > 0:
                expected_sgk = round(row["brut"] * 0.14, 2)
                assert abs(row["sgk"] - expected_sgk) <= 0.01, f"SGK rate mismatch for {row.get('staff_name')}"
    
    def test_issizlik_rate_1_percent(self, auth_headers):
        """İşsizlik deduction is 1% of gross"""
        resp = requests.get(
            f"{BASE_URL}/api/payroll/preview/all?month=2026-05",
            headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        
        for row in data["rows"]:
            if row["brut"] > 0:
                expected_issizlik = round(row["brut"] * 0.01, 2)
                assert abs(row["issizlik"] - expected_issizlik) <= 0.01, f"İşsizlik rate mismatch for {row.get('staff_name')}"
    
    def test_gelir_vergisi_rate_15_percent_of_taxbase(self, auth_headers):
        """Gelir Vergisi is 15% of (brut - sgk - issizlik)"""
        resp = requests.get(
            f"{BASE_URL}/api/payroll/preview/all?month=2026-05",
            headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        
        for row in data["rows"]:
            if row["brut"] > 0:
                tax_base = row["brut"] - row["sgk"] - row["issizlik"]
                expected_gelir = round(max(0, tax_base) * 0.15, 2)
                assert abs(row["gelir_vergisi"] - expected_gelir) <= 0.01, f"Gelir Vergisi mismatch for {row.get('staff_name')}"
    
    def test_damga_vergisi_rate_0759_percent(self, auth_headers):
        """Damga Vergisi is 0.759% of gross"""
        resp = requests.get(
            f"{BASE_URL}/api/payroll/preview/all?month=2026-05",
            headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        
        for row in data["rows"]:
            if row["brut"] > 0:
                expected_damga = round(row["brut"] * 0.00759, 2)
                assert abs(row["damga_vergisi"] - expected_damga) <= 0.01, f"Damga Vergisi mismatch for {row.get('staff_name')}"


class TestPayrollDataIntegrity:
    """Test data integrity and edge cases"""
    
    def test_preview_returns_employee_info(self, auth_headers):
        """Preview includes staff_id, staff_name, role for each row"""
        resp = requests.get(
            f"{BASE_URL}/api/payroll/preview/all?month=2026-05",
            headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        
        for row in data["rows"]:
            assert "staff_id" in row
            assert "staff_name" in row
            assert "role" in row
    
    def test_preview_returns_shift_count_and_hours(self, auth_headers):
        """Preview includes shift_count and total_hours"""
        resp = requests.get(
            f"{BASE_URL}/api/payroll/preview/all?month=2026-05",
            headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        
        for row in data["rows"]:
            assert "shift_count" in row
            assert "total_hours" in row
            assert isinstance(row["shift_count"], int) or isinstance(row["shift_count"], float)
            assert isinstance(row["total_hours"], (int, float))
    
    def test_totals_include_shift_count(self, auth_headers):
        """Totals include shift_count and total_hours"""
        resp = requests.get(
            f"{BASE_URL}/api/payroll/preview/all?month=2026-05",
            headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        totals = data["totals"]
        
        assert "shift_count" in totals
        assert "total_hours" in totals


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
