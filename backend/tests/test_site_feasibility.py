"""
Site Feasibility & Investor Analysis API Tests
Tests for Batch 38 - Pasha Hotel investor analysis module

Endpoints tested:
- POST /api/feasibility/analysis - create study
- GET /api/feasibility/analyses/{property_id} - list studies
- GET /api/feasibility/analysis/{id} - single study
- PUT /api/feasibility/analysis/{id} - update study
- DELETE /api/feasibility/analysis/{id} - delete study
- GET /api/feasibility/analysis/{id}/hurdle - 4x lease hurdle test
- GET /api/feasibility/analysis/{id}/sensitivity - occupancy sensitivity
- GET /api/feasibility/analysis/{id}/ramp-up - Y1 ramp-up working capital
- GET /api/feasibility/analysis/{id}/ota-risk - wholesaler/OTA haircut risk
- GET /api/feasibility/analysis/{id}/adr-curve - day-of-week ADR curve
- POST /api/feasibility/analysis/{id}/scrape - mock comp scrape
- POST /api/feasibility/analysis/{id}/verdict - AI investor verdict
- GET /api/feasibility/analysis/{id}/pdf - investor PDF export
- GET /api/feasibility/dashboard/{property_id} - dashboard summary
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test data matching Pasha Hotel PDF: 30 rooms, ADR £88, 75% occ, £180k lease, 4x target
PASHA_STUDY_DATA = {
    "property_id": "TEST_feasibility_prop",
    "project_name": "TEST_Pasha Hotel SE17",
    "location": "London SE17",
    "currency": "GBP",
    "rooms": 30,
    "target_adr": 88.0,
    "target_occupancy_pct": 75.0,
    "annual_lease_cost": 180000.0,
    "lease_multiple_target": 4.0,
    "ota_commission_pct": 15.0,
    "wholesaler_share_pct": 10.0,
    "wholesaler_haircut_pct": 10.0,
    "ramp_up_months": 15,
    "ramp_start_occupancy_pct": 40.0,
    "comp_set": [
        {"name": "Premier Inn Elephant", "rooms": 120, "adr": 95.0, "occupancy_pct": 82.0},
        {"name": "Travelodge Southwark", "rooms": 80, "adr": 75.0, "occupancy_pct": 78.0},
    ],
    "notes": "Test study for Pasha Hotel investor analysis"
}


@pytest.fixture(scope="module")
def auth_session():
    """Authenticate and return session with cookies"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    
    if login_resp.status_code != 200:
        pytest.skip(f"Auth failed: {login_resp.status_code} - {login_resp.text}")
    
    return session


@pytest.fixture(scope="module")
def created_study(auth_session):
    """Create a study for testing and clean up after"""
    resp = auth_session.post(f"{BASE_URL}/api/feasibility/analysis", json=PASHA_STUDY_DATA)
    assert resp.status_code == 200, f"Failed to create study: {resp.text}"
    study = resp.json()
    
    yield study
    
    # Cleanup
    auth_session.delete(f"{BASE_URL}/api/feasibility/analysis/{study['id']}")


class TestFeasibilityCreate:
    """POST /api/feasibility/analysis - create study"""
    
    def test_create_study_returns_all_computed_fields(self, auth_session):
        """Create study should return hurdle, sensitivity, ota_risk, ramp_up, adr_curve, scrape"""
        resp = auth_session.post(f"{BASE_URL}/api/feasibility/analysis", json=PASHA_STUDY_DATA)
        assert resp.status_code == 200
        
        data = resp.json()
        
        # Verify all computed sections are present
        assert "id" in data
        assert "hurdle" in data
        assert "sensitivity" in data
        assert "ota_risk" in data
        assert "ramp_up" in data
        assert "adr_curve" in data
        assert "scrape" in data
        assert "per_key_revenue" in data
        
        # Cleanup
        auth_session.delete(f"{BASE_URL}/api/feasibility/analysis/{data['id']}")
    
    def test_create_study_pasha_numbers(self, auth_session):
        """Verify Pasha Hotel numbers: turnover≈722,700, hurdle=720k, headroom≈2,700"""
        resp = auth_session.post(f"{BASE_URL}/api/feasibility/analysis", json=PASHA_STUDY_DATA)
        assert resp.status_code == 200
        
        data = resp.json()
        hurdle = data["hurdle"]
        
        # Expected: 88 * 0.75 * 30 * 365 = 722,700
        assert hurdle["annual_turnover"] == 722700.0, f"Expected 722700, got {hurdle['annual_turnover']}"
        
        # Hurdle target: 180000 * 4 = 720000
        assert hurdle["hurdle_target"] == 720000.0, f"Expected 720000, got {hurdle['hurdle_target']}"
        
        # Headroom: 722700 - 720000 = 2700
        assert hurdle["headroom"] == 2700.0, f"Expected 2700, got {hurdle['headroom']}"
        
        # Lease multiple: 722700 / 180000 ≈ 4.015
        assert 4.0 <= hurdle["lease_multiple"] <= 4.02, f"Expected ~4.01, got {hurdle['lease_multiple']}"
        
        # Verdict should be "on-the-line" (headroom < 5% of hurdle)
        assert hurdle["verdict"] == "on-the-line", f"Expected on-the-line, got {hurdle['verdict']}"
        
        # Per-key revenue: 88 * 0.75 * 365 = 24,090
        assert data["per_key_revenue"] == 24090.0, f"Expected 24090, got {data['per_key_revenue']}"
        
        # Cleanup
        auth_session.delete(f"{BASE_URL}/api/feasibility/analysis/{data['id']}")
    
    def test_create_study_sensitivity_default_11_items(self, auth_session):
        """Sensitivity should have 11 items (±5pp) by default"""
        resp = auth_session.post(f"{BASE_URL}/api/feasibility/analysis", json=PASHA_STUDY_DATA)
        assert resp.status_code == 200
        
        data = resp.json()
        sensitivity = data["sensitivity"]
        
        assert len(sensitivity) == 11, f"Expected 11 sensitivity items, got {len(sensitivity)}"
        
        # Check delta_pp range from -5 to +5
        deltas = [s["delta_pp"] for s in sensitivity]
        assert deltas == list(range(-5, 6)), f"Expected -5 to +5, got {deltas}"
        
        # Cleanup
        auth_session.delete(f"{BASE_URL}/api/feasibility/analysis/{data['id']}")


class TestFeasibilityList:
    """GET /api/feasibility/analyses/{property_id} - list studies"""
    
    def test_list_studies(self, auth_session, created_study):
        """List studies for property"""
        resp = auth_session.get(f"{BASE_URL}/api/feasibility/analyses/{PASHA_STUDY_DATA['property_id']}")
        assert resp.status_code == 200
        
        data = resp.json()
        assert "items" in data
        assert "count" in data
        assert data["count"] >= 1
        
        # Verify our study is in the list
        study_ids = [s["id"] for s in data["items"]]
        assert created_study["id"] in study_ids


class TestFeasibilityGet:
    """GET /api/feasibility/analysis/{id} - single study"""
    
    def test_get_study(self, auth_session, created_study):
        """Get single study by ID"""
        resp = auth_session.get(f"{BASE_URL}/api/feasibility/analysis/{created_study['id']}")
        assert resp.status_code == 200
        
        data = resp.json()
        assert data["id"] == created_study["id"]
        assert data["project_name"] == PASHA_STUDY_DATA["project_name"]
    
    def test_get_study_not_found(self, auth_session):
        """Get non-existent study returns 404"""
        resp = auth_session.get(f"{BASE_URL}/api/feasibility/analysis/nonexistent-id")
        assert resp.status_code == 404


class TestFeasibilityHurdle:
    """GET /api/feasibility/analysis/{id}/hurdle - 4x lease hurdle test"""
    
    def test_hurdle_endpoint(self, auth_session, created_study):
        """Hurdle endpoint returns correct structure"""
        resp = auth_session.get(f"{BASE_URL}/api/feasibility/analysis/{created_study['id']}/hurdle")
        assert resp.status_code == 200
        
        data = resp.json()
        
        # Required fields
        assert "annual_turnover" in data
        assert "hurdle_target" in data
        assert "headroom" in data
        assert "lease_multiple" in data
        assert "verdict" in data
        assert "passes" in data
        
        # Verify verdict is one of expected values
        valid_verdicts = ["fails", "on-the-line", "marginal-pass", "comfortable-pass", "no-lease"]
        assert data["verdict"] in valid_verdicts


class TestFeasibilitySensitivity:
    """GET /api/feasibility/analysis/{id}/sensitivity - occupancy sensitivity"""
    
    def test_sensitivity_default_span(self, auth_session, created_study):
        """Sensitivity with default span=5 returns 11 items"""
        resp = auth_session.get(f"{BASE_URL}/api/feasibility/analysis/{created_study['id']}/sensitivity")
        assert resp.status_code == 200
        
        data = resp.json()
        assert "items" in data
        assert len(data["items"]) == 11
    
    def test_sensitivity_custom_span(self, auth_session, created_study):
        """Sensitivity with span=3 returns 7 items"""
        resp = auth_session.get(f"{BASE_URL}/api/feasibility/analysis/{created_study['id']}/sensitivity?span=3")
        assert resp.status_code == 200
        
        data = resp.json()
        assert "items" in data
        assert len(data["items"]) == 7  # 2*3+1 = 7
        
        # Check structure
        for item in data["items"]:
            assert "delta_pp" in item
            assert "occupancy_pct" in item
            assert "headroom" in item
            assert "passes" in item


class TestFeasibilityRampUp:
    """GET /api/feasibility/analysis/{id}/ramp-up - Y1 ramp-up working capital"""
    
    def test_ramp_up_endpoint(self, auth_session, created_study):
        """Ramp-up returns schedule and working capital"""
        resp = auth_session.get(f"{BASE_URL}/api/feasibility/analysis/{created_study['id']}/ramp-up")
        assert resp.status_code == 200
        
        data = resp.json()
        
        assert "months" in data
        assert "schedule" in data
        assert "working_capital_required" in data
        
        # Schedule should have entries for each month
        assert len(data["schedule"]) == data["months"]
        
        # Each schedule entry should have required fields
        for entry in data["schedule"]:
            assert "month" in entry
            assert "occupancy_pct" in entry
            assert "revenue" in entry
            assert "opex" in entry
            assert "lease" in entry
            assert "net" in entry


class TestFeasibilityOtaRisk:
    """GET /api/feasibility/analysis/{id}/ota-risk - wholesaler/OTA haircut risk"""
    
    def test_ota_risk_endpoint(self, auth_session, created_study):
        """OTA risk returns turnover_after_haircut, headroom_after_haircut, still_passes"""
        resp = auth_session.get(f"{BASE_URL}/api/feasibility/analysis/{created_study['id']}/ota-risk")
        assert resp.status_code == 200
        
        data = resp.json()
        
        assert "turnover_after_haircut" in data
        assert "headroom_after_haircut" in data
        assert "still_passes" in data
        assert "wholesaler_share_pct" in data
        assert "wholesaler_haircut_pct" in data


class TestFeasibilityAdrCurve:
    """GET /api/feasibility/analysis/{id}/adr-curve - day-of-week ADR curve"""
    
    def test_adr_curve_endpoint(self, auth_session, created_study):
        """ADR curve returns by_dow with 7 days"""
        resp = auth_session.get(f"{BASE_URL}/api/feasibility/analysis/{created_study['id']}/adr-curve")
        assert resp.status_code == 200
        
        data = resp.json()
        
        assert "by_dow" in data
        assert len(data["by_dow"]) == 7
        
        # Check all days present
        expected_days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for day in expected_days:
            assert day in data["by_dow"]
        
        assert "weekly_avg" in data
        assert "currency" in data


class TestFeasibilityScrape:
    """POST /api/feasibility/analysis/{id}/scrape - mock comp scrape"""
    
    def test_scrape_endpoint(self, auth_session, created_study):
        """Scrape returns mock comp-set data"""
        resp = auth_session.post(f"{BASE_URL}/api/feasibility/analysis/{created_study['id']}/scrape")
        assert resp.status_code == 200
        
        data = resp.json()
        
        assert "scrape_window" in data
        assert "comp_results" in data
        assert "comp_avg_adr" in data
        assert "comp_avg_occupancy" in data
        assert "source" in data
        
        # Source should indicate mock
        assert "mock" in data["source"].lower()


class TestFeasibilityVerdict:
    """POST /api/feasibility/analysis/{id}/verdict - AI investor verdict"""
    
    def test_verdict_endpoint(self, auth_session, created_study):
        """Verdict returns AI narrative with available=true"""
        resp = auth_session.post(f"{BASE_URL}/api/feasibility/analysis/{created_study['id']}/verdict")
        assert resp.status_code == 200
        
        data = resp.json()
        
        assert "narrative" in data
        assert "available" in data
        
        # If LLM is available, narrative should be non-empty
        if data["available"]:
            assert len(data["narrative"]) > 50, "AI narrative should be substantial"
            assert "model" in data


class TestFeasibilityPdf:
    """GET /api/feasibility/analysis/{id}/pdf - investor PDF export"""
    
    def test_pdf_endpoint(self, auth_session, created_study):
        """PDF export returns application/pdf > 5KB"""
        resp = auth_session.get(f"{BASE_URL}/api/feasibility/analysis/{created_study['id']}/pdf")
        assert resp.status_code == 200
        
        # Check content type
        assert "application/pdf" in resp.headers.get("Content-Type", "")
        
        # Check size > 5KB
        content_length = len(resp.content)
        assert content_length > 5000, f"PDF should be > 5KB, got {content_length} bytes"
        
        # Check PDF magic bytes
        assert resp.content[:4] == b"%PDF", "Response should be valid PDF"


class TestFeasibilityDashboard:
    """GET /api/feasibility/dashboard/{property_id} - dashboard summary"""
    
    def test_dashboard_endpoint(self, auth_session, created_study):
        """Dashboard returns total/passing/failing/latest"""
        resp = auth_session.get(f"{BASE_URL}/api/feasibility/dashboard/{PASHA_STUDY_DATA['property_id']}")
        assert resp.status_code == 200
        
        data = resp.json()
        
        assert "total" in data
        assert "passing" in data
        assert "failing" in data
        assert "latest" in data
        
        assert data["total"] >= 1
        assert isinstance(data["latest"], list)


class TestFeasibilityUpdate:
    """PUT /api/feasibility/analysis/{id} - update study"""
    
    def test_update_study_recomputes(self, auth_session):
        """Update study recomputes all derived fields"""
        # Create a study
        resp = auth_session.post(f"{BASE_URL}/api/feasibility/analysis", json=PASHA_STUDY_DATA)
        assert resp.status_code == 200
        study = resp.json()
        
        # Update with higher ADR
        update_data = {**PASHA_STUDY_DATA, "target_adr": 100.0}
        resp = auth_session.put(f"{BASE_URL}/api/feasibility/analysis/{study['id']}", json=update_data)
        assert resp.status_code == 200
        
        updated = resp.json()
        
        # New turnover: 100 * 0.75 * 30 * 365 = 821,250
        assert updated["hurdle"]["annual_turnover"] == 821250.0
        
        # Cleanup
        auth_session.delete(f"{BASE_URL}/api/feasibility/analysis/{study['id']}")


class TestFeasibilityDelete:
    """DELETE /api/feasibility/analysis/{id} - delete study"""
    
    def test_delete_study(self, auth_session):
        """Delete study removes it"""
        # Create a study
        resp = auth_session.post(f"{BASE_URL}/api/feasibility/analysis", json=PASHA_STUDY_DATA)
        assert resp.status_code == 200
        study = resp.json()
        
        # Delete it
        resp = auth_session.delete(f"{BASE_URL}/api/feasibility/analysis/{study['id']}")
        assert resp.status_code == 200
        
        # Verify it's gone
        resp = auth_session.get(f"{BASE_URL}/api/feasibility/analysis/{study['id']}")
        assert resp.status_code == 404
    
    def test_delete_not_found(self, auth_session):
        """Delete non-existent study returns 404"""
        resp = auth_session.delete(f"{BASE_URL}/api/feasibility/analysis/nonexistent-id")
        assert resp.status_code == 404


class TestFeasibilityAuth:
    """Authentication tests"""
    
    def test_unauthenticated_create_fails(self):
        """Create without auth returns 401"""
        session = requests.Session()
        resp = session.post(f"{BASE_URL}/api/feasibility/analysis", json=PASHA_STUDY_DATA)
        assert resp.status_code == 401
    
    def test_unauthenticated_list_fails(self):
        """List without auth returns 401"""
        session = requests.Session()
        resp = session.get(f"{BASE_URL}/api/feasibility/analyses/test-prop")
        assert resp.status_code == 401
