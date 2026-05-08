"""
Iteration 227 - Batch 15: EU Compliance Hub
Tests for 7-country e-Invoice XML + Police reporting exports
Countries: IT, ES, FR, GR, HU, PL, MX
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

@pytest.fixture(scope="module")
def auth_token():
    """Get admin auth token"""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.cookies.get("access_token") or resp.json().get("access_token")

@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Auth headers with token"""
    return {"Cookie": f"access_token={auth_token}"}


class TestEUComplianceCatalog:
    """Test GET /api/eu-compliance/catalog"""
    
    def test_catalog_returns_7_countries(self, auth_headers):
        """Catalog should return 7 countries with correct metadata"""
        resp = requests.get(f"{BASE_URL}/api/eu-compliance/catalog", headers=auth_headers)
        assert resp.status_code == 200, f"Catalog failed: {resp.text}"
        
        data = resp.json()
        assert "countries" in data
        countries = data["countries"]
        
        # Verify 7 countries
        expected_codes = ["it", "es", "fr", "gr", "hu", "pl", "mx"]
        assert len(countries) == 7, f"Expected 7 countries, got {len(countries)}"
        for code in expected_codes:
            assert code in countries, f"Missing country: {code}"
    
    def test_catalog_country_structure(self, auth_headers):
        """Each country should have name, flag, invoice, and optional police"""
        resp = requests.get(f"{BASE_URL}/api/eu-compliance/catalog", headers=auth_headers)
        data = resp.json()["countries"]
        
        # Italy - has both invoice and police
        it = data["it"]
        assert it["name"] == "Italia"
        assert it["flag"] == "🇮🇹"
        assert "invoice" in it and it["invoice"] is not None
        assert it["invoice"]["scheme"] == "FatturaPA 1.2 XML (Sistema di Interscambio / SDI)"
        assert it["invoice"]["format"] == "xml"
        assert "police" in it and it["police"] is not None
        assert it["police"]["scheme"] == "Alloggiati Web (Polizia di Stato)"
        assert it["police"]["format"] == "txt"
        
        # Spain - has both
        es = data["es"]
        assert es["name"] == "España"
        assert es["flag"] == "🇪🇸"
        assert es["invoice"] is not None
        assert es["police"] is not None
        
        # France - has both
        fr = data["fr"]
        assert fr["name"] == "France"
        assert fr["flag"] == "🇫🇷"
        assert fr["invoice"] is not None
        assert fr["police"] is not None
        
        # Greece - has both
        gr = data["gr"]
        assert gr["name"] == "Ελλάδα"
        assert gr["flag"] == "🇬🇷"
        assert gr["invoice"] is not None
        assert gr["police"] is not None
        
        # Hungary - invoice only, NO police
        hu = data["hu"]
        assert hu["name"] == "Magyarország"
        assert hu["flag"] == "🇭🇺"
        assert hu["invoice"] is not None
        assert hu["police"] is None
        
        # Poland - invoice only, NO police
        pl = data["pl"]
        assert pl["name"] == "Polska"
        assert pl["flag"] == "🇵🇱"
        assert pl["invoice"] is not None
        assert pl["police"] is None
        
        # Mexico - invoice only, NO police
        mx = data["mx"]
        assert mx["name"] == "México"
        assert mx["flag"] == "🇲🇽"
        assert mx["invoice"] is not None
        assert mx["police"] is None


class TestItalyInvoiceExport:
    """Test Italy FatturaPA XML export"""
    
    def test_italy_invoice_export(self, auth_headers):
        """POST /api/eu-compliance/export country=it kind=invoice → FatturaPA XML"""
        resp = requests.post(f"{BASE_URL}/api/eu-compliance/export", headers=auth_headers, json={
            "property_id": "default",
            "country": "it",
            "kind": "invoice",
            "from_date": "2026-01-01",
            "to_date": "2026-12-31"
        })
        assert resp.status_code == 200, f"Italy invoice export failed: {resp.text}"
        
        data = resp.json()
        assert "files" in data
        assert "file_count" in data
        assert "total_amount" in data
        assert data["scheme"] == "FatturaPA 1.2 XML (Sistema di Interscambio / SDI)"
        
        # If there are files, verify XML structure
        if data["files"]:
            first_file = data["files"][0]
            assert "filename" in first_file
            assert first_file["filename"].endswith(".xml")
            assert "content" in first_file
            content = first_file["content"]
            # Verify FatturaPA structure
            assert 'versione="FPR12"' in content, "Missing FPR12 version"
            assert "CedentePrestatore" in content, "Missing CedentePrestatore"
            assert "DettaglioLinee" in content, "Missing DettaglioLinee"
            assert "total" in first_file


class TestSpainExports:
    """Test Spain invoice and police exports"""
    
    def test_spain_invoice_ubl_xml(self, auth_headers):
        """POST /api/eu-compliance/export country=es kind=invoice → UBL XML with PEPPOL"""
        resp = requests.post(f"{BASE_URL}/api/eu-compliance/export", headers=auth_headers, json={
            "property_id": "default",
            "country": "es",
            "kind": "invoice",
            "from_date": "2026-01-01",
            "to_date": "2026-12-31"
        })
        assert resp.status_code == 200, f"Spain invoice export failed: {resp.text}"
        
        data = resp.json()
        if data["files"]:
            content = data["files"][0]["content"]
            # Verify UBL structure with PEPPOL ProfileID
            assert "ProfileID" in content, "Missing ProfileID"
            assert "peppol" in content.lower(), "Missing PEPPOL reference"
            assert "EUR" in content, "Missing EUR currency"
    
    def test_spain_police_csv(self, auth_headers):
        """POST /api/eu-compliance/export country=es kind=police → CSV with ; delimiter"""
        resp = requests.post(f"{BASE_URL}/api/eu-compliance/export", headers=auth_headers, json={
            "property_id": "default",
            "country": "es",
            "kind": "police",
            "from_date": "2026-01-01",
            "to_date": "2026-12-31"
        })
        assert resp.status_code == 200, f"Spain police export failed: {resp.text}"
        
        data = resp.json()
        assert "content" in data
        assert "filename" in data
        assert data["filename"].endswith(".csv")
        
        content = data["content"]
        # Verify CSV header starts with expected columns
        assert content.startswith("establecimiento_id;referencia_reserva"), \
            f"Spain police CSV header incorrect: {content[:100]}"


class TestItalyPoliceExport:
    """Test Italy Alloggiati fixed-width TXT export"""
    
    def test_italy_police_txt(self, auth_headers):
        """POST /api/eu-compliance/export country=it kind=police → 170-char fixed-width TXT"""
        resp = requests.post(f"{BASE_URL}/api/eu-compliance/export", headers=auth_headers, json={
            "property_id": "default",
            "country": "it",
            "kind": "police",
            "from_date": "2026-01-01",
            "to_date": "2026-12-31"
        })
        assert resp.status_code == 200, f"Italy police export failed: {resp.text}"
        
        data = resp.json()
        assert "content" in data
        assert "filename" in data
        assert data["filename"].endswith(".txt")
        assert data["format"] == "txt"
        
        content = data["content"]
        # If there are lines, verify format
        if content.strip():
            lines = content.strip().split("\n")
            for line in lines:
                # Record type 16 at start
                assert line.startswith("16"), f"Line should start with record type 16: {line[:20]}"


class TestFrancePoliceExport:
    """Test France fiche de police CSV export"""
    
    def test_france_police_csv(self, auth_headers):
        """POST /api/eu-compliance/export country=fr kind=police → CSV with French headers"""
        resp = requests.post(f"{BASE_URL}/api/eu-compliance/export", headers=auth_headers, json={
            "property_id": "default",
            "country": "fr",
            "kind": "police",
            "from_date": "2026-01-01",
            "to_date": "2026-12-31"
        })
        assert resp.status_code == 200, f"France police export failed: {resp.text}"
        
        data = resp.json()
        assert "content" in data
        content = data["content"]
        # Verify French CSV headers
        assert "nom;prenom;date_naissance" in content, \
            f"France police CSV header incorrect: {content[:100]}"


class TestGreecePoliceExport:
    """Test Greece tourism police CSV export"""
    
    def test_greece_police_csv(self, auth_headers):
        """POST /api/eu-compliance/export country=gr kind=police → CSV with Greek headers"""
        resp = requests.post(f"{BASE_URL}/api/eu-compliance/export", headers=auth_headers, json={
            "property_id": "default",
            "country": "gr",
            "kind": "police",
            "from_date": "2026-01-01",
            "to_date": "2026-12-31"
        })
        assert resp.status_code == 200, f"Greece police export failed: {resp.text}"
        
        data = resp.json()
        assert "content" in data
        content = data["content"]
        # Verify Greek CSV headers
        assert "hotel_id;booking_ref;guest_surname" in content, \
            f"Greece police CSV header incorrect: {content[:100]}"


class TestHungaryPoliceRestriction:
    """Test Hungary police export returns 400 (not required)"""
    
    def test_hungary_police_returns_400(self, auth_headers):
        """POST /api/eu-compliance/export country=hu kind=police → 400"""
        resp = requests.post(f"{BASE_URL}/api/eu-compliance/export", headers=auth_headers, json={
            "property_id": "default",
            "country": "hu",
            "kind": "police",
            "from_date": "2026-01-01",
            "to_date": "2026-12-31"
        })
        assert resp.status_code == 400, f"Hungary police should return 400, got {resp.status_code}"
        assert "does not require police" in resp.text.lower() or "hu" in resp.text.lower()


class TestValidationErrors:
    """Test validation error handling"""
    
    def test_invalid_country_returns_400(self, auth_headers):
        """POST /api/eu-compliance/export country=xx → 400"""
        resp = requests.post(f"{BASE_URL}/api/eu-compliance/export", headers=auth_headers, json={
            "property_id": "default",
            "country": "xx",
            "kind": "invoice",
            "from_date": "2026-01-01",
            "to_date": "2026-12-31"
        })
        assert resp.status_code == 400, f"Invalid country should return 400, got {resp.status_code}"
    
    def test_invalid_kind_returns_400(self, auth_headers):
        """POST /api/eu-compliance/export kind=invalid → 400"""
        resp = requests.post(f"{BASE_URL}/api/eu-compliance/export", headers=auth_headers, json={
            "property_id": "default",
            "country": "it",
            "kind": "invalid",
            "from_date": "2026-01-01",
            "to_date": "2026-12-31"
        })
        assert resp.status_code == 400, f"Invalid kind should return 400, got {resp.status_code}"
    
    def test_invalid_date_format_returns_400(self, auth_headers):
        """POST /api/eu-compliance/export with invalid date → 400"""
        resp = requests.post(f"{BASE_URL}/api/eu-compliance/export", headers=auth_headers, json={
            "property_id": "default",
            "country": "it",
            "kind": "invoice",
            "from_date": "01-01-2026",  # Wrong format
            "to_date": "2026-12-31"
        })
        assert resp.status_code == 400, f"Invalid date should return 400, got {resp.status_code}"


class TestExportHistory:
    """Test export history endpoint"""
    
    def test_history_endpoint(self, auth_headers):
        """GET /api/eu-compliance/{property_id}/history → history[]"""
        resp = requests.get(f"{BASE_URL}/api/eu-compliance/default/history", headers=auth_headers)
        assert resp.status_code == 200, f"History failed: {resp.text}"
        
        data = resp.json()
        assert "history" in data
        assert isinstance(data["history"], list)


class TestRegressionBatch14:
    """Regression tests for Batch 14 AI Predictions"""
    
    def test_ai_predictions_cancel_risk(self, auth_headers):
        """GET /api/ai-predictions/cancel-risk/{property_id} still works"""
        resp = requests.get(
            f"{BASE_URL}/api/ai-predictions/cancel-risk/default?days_ahead=60&min_score=30",
            headers=auth_headers
        )
        assert resp.status_code == 200, f"AI Predictions cancel-risk failed: {resp.text}"
        data = resp.json()
        assert "rows" in data or "by_band" in data


class TestRegressionBatch13:
    """Regression tests for Batch 13 TR Compliance"""
    
    def test_tr_compliance_kbs_export(self, auth_headers):
        """POST /api/tr-compliance/kbs/export still works"""
        resp = requests.post(f"{BASE_URL}/api/tr-compliance/kbs/export", headers=auth_headers, json={
            "property_id": "default",
            "from_date": "2026-01-01",
            "to_date": "2026-01-31"
        })
        # Should return 200 (may have empty data)
        assert resp.status_code == 200, f"TR Compliance KBS export failed: {resp.text}"


class TestRegressionCommandPalette:
    """Regression test for Today Hub - verify todays-actions API"""
    
    def test_todays_actions_api(self, auth_headers):
        """GET /api/bookings/timeline/{property_id}/todays-actions still works"""
        resp = requests.get(
            f"{BASE_URL}/api/bookings/timeline/default/todays-actions",
            headers=auth_headers
        )
        assert resp.status_code == 200, f"Today's Actions API failed: {resp.text}"
