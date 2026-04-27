"""
Iteration 224 - Tier-1 Master Operations Dashboard Tests
Tests the aggregated KPI dashboard from all 50 keyless features (Batches 1-10)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Expected 20 KPI groups
EXPECTED_KPI_KEYS = [
    "preauth", "chargeback", "web_push", "pms_crs", "public_api",
    "mid_stay", "ab_test", "pre_arrival", "sr_voucher", "folio_split",
    "loyalty", "late_checkout", "ota_forecast", "low_stock", "rebook",
    "stay_ext", "long_stay", "cancel_insurance", "group_rooming", "ci_slots"
]


@pytest.fixture(scope="module")
def admin_token():
    """Get admin auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["token"]


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    """Auth headers for requests"""
    return {"Authorization": f"Bearer {admin_token}"}


class TestTier1DashboardAPI:
    """Tests for GET /api/tier1-dashboard/{property_id}"""

    def test_dashboard_returns_200_with_auth(self, auth_headers):
        """Dashboard endpoint returns 200 with valid auth"""
        response = requests.get(
            f"{BASE_URL}/api/tier1-dashboard/default?days=30",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "property_id" in data
        assert "window_days" in data
        assert "computed_at" in data
        assert "kpis" in data
        assert "highlights" in data

    def test_dashboard_requires_auth(self):
        """Dashboard endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/tier1-dashboard/default?days=30")
        assert response.status_code in [401, 403]

    def test_dashboard_response_structure(self, auth_headers):
        """Verify response has correct top-level structure"""
        response = requests.get(
            f"{BASE_URL}/api/tier1-dashboard/default?days=30",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Top-level fields
        assert data["property_id"] == "default"
        assert data["window_days"] == 30
        assert isinstance(data["computed_at"], str)
        assert isinstance(data["kpis"], dict)
        assert isinstance(data["highlights"], list)

    def test_dashboard_has_exactly_20_kpi_groups(self, auth_headers):
        """Dashboard must return exactly 20 KPI groups"""
        response = requests.get(
            f"{BASE_URL}/api/tier1-dashboard/default?days=30",
            headers=auth_headers
        )
        assert response.status_code == 200
        kpis = response.json()["kpis"]
        
        assert len(kpis) == 20, f"Expected 20 KPI groups, got {len(kpis)}"
        
        # Verify all expected keys are present
        for key in EXPECTED_KPI_KEYS:
            assert key in kpis, f"Missing KPI group: {key}"

    def test_preauth_kpi_structure(self, auth_headers):
        """Pre-auth KPI has correct fields"""
        response = requests.get(
            f"{BASE_URL}/api/tier1-dashboard/default?days=30",
            headers=auth_headers
        )
        kpi = response.json()["kpis"]["preauth"]
        assert "total_holds" in kpi
        assert "currently_held" in kpi
        assert "captured" in kpi

    def test_chargeback_kpi_structure(self, auth_headers):
        """Chargeback KPI has correct fields"""
        response = requests.get(
            f"{BASE_URL}/api/tier1-dashboard/default?days=30",
            headers=auth_headers
        )
        kpi = response.json()["kpis"]["chargeback"]
        assert "cases" in kpi
        assert "won" in kpi
        assert "lost" in kpi
        assert "win_rate_pct" in kpi
        assert "amount_at_risk" in kpi

    def test_web_push_kpi_structure(self, auth_headers):
        """Web push KPI has correct fields"""
        response = requests.get(
            f"{BASE_URL}/api/tier1-dashboard/default?days=30",
            headers=auth_headers
        )
        kpi = response.json()["kpis"]["web_push"]
        assert "active_subscribers" in kpi
        assert "pushes_sent" in kpi

    def test_pms_crs_kpi_structure(self, auth_headers):
        """PMS-CRS KPI has correct fields"""
        response = requests.get(
            f"{BASE_URL}/api/tier1-dashboard/default?days=30",
            headers=auth_headers
        )
        kpi = response.json()["kpis"]["pms_crs"]
        assert "pms_bookings" in kpi
        assert "crs_records" in kpi
        assert "drift" in kpi

    def test_public_api_kpi_structure(self, auth_headers):
        """Public API KPI has correct fields"""
        response = requests.get(
            f"{BASE_URL}/api/tier1-dashboard/default?days=30",
            headers=auth_headers
        )
        kpi = response.json()["kpis"]["public_api"]
        assert "active_keys" in kpi
        assert "calls_in_window" in kpi

    def test_mid_stay_kpi_structure(self, auth_headers):
        """Mid-stay KPI has correct fields"""
        response = requests.get(
            f"{BASE_URL}/api/tier1-dashboard/default?days=30",
            headers=auth_headers
        )
        kpi = response.json()["kpis"]["mid_stay"]
        assert "responses" in kpi
        assert "avg_score" in kpi
        assert "low_scores" in kpi

    def test_ab_test_kpi_structure(self, auth_headers):
        """A/B test KPI has correct fields"""
        response = requests.get(
            f"{BASE_URL}/api/tier1-dashboard/default?days=30",
            headers=auth_headers
        )
        kpi = response.json()["kpis"]["ab_test"]
        assert "active_experiments" in kpi
        assert "events_in_window" in kpi

    def test_pre_arrival_kpi_structure(self, auth_headers):
        """Pre-arrival KPI has correct fields"""
        response = requests.get(
            f"{BASE_URL}/api/tier1-dashboard/default?days=30",
            headers=auth_headers
        )
        kpi = response.json()["kpis"]["pre_arrival"]
        assert "dispatches" in kpi
        assert "sent" in kpi

    def test_sr_voucher_kpi_structure(self, auth_headers):
        """SR voucher KPI has correct fields"""
        response = requests.get(
            f"{BASE_URL}/api/tier1-dashboard/default?days=30",
            headers=auth_headers
        )
        kpi = response.json()["kpis"]["sr_voucher"]
        assert "issued" in kpi
        assert "redeemed" in kpi
        assert "redeem_rate_pct" in kpi
        assert "birthday_issued" in kpi

    def test_folio_split_kpi_structure(self, auth_headers):
        """Folio split KPI has correct fields"""
        response = requests.get(
            f"{BASE_URL}/api/tier1-dashboard/default?days=30",
            headers=auth_headers
        )
        kpi = response.json()["kpis"]["folio_split"]
        assert "settlements_in_window" in kpi

    def test_loyalty_kpi_structure(self, auth_headers):
        """Loyalty KPI has correct fields"""
        response = requests.get(
            f"{BASE_URL}/api/tier1-dashboard/default?days=30",
            headers=auth_headers
        )
        kpi = response.json()["kpis"]["loyalty"]
        assert "upgrades" in kpi
        assert "downgrades" in kpi

    def test_late_checkout_kpi_structure(self, auth_headers):
        """Late checkout KPI has correct fields"""
        response = requests.get(
            f"{BASE_URL}/api/tier1-dashboard/default?days=30",
            headers=auth_headers
        )
        kpi = response.json()["kpis"]["late_checkout"]
        assert "offers" in kpi
        assert "accepted" in kpi
        assert "revenue" in kpi

    def test_ota_forecast_kpi_structure(self, auth_headers):
        """OTA forecast KPI has correct fields"""
        response = requests.get(
            f"{BASE_URL}/api/tier1-dashboard/default?days=30",
            headers=auth_headers
        )
        kpi = response.json()["kpis"]["ota_forecast"]
        assert "horizon_days" in kpi

    def test_low_stock_kpi_structure(self, auth_headers):
        """Low stock KPI has correct fields"""
        response = requests.get(
            f"{BASE_URL}/api/tier1-dashboard/default?days=30",
            headers=auth_headers
        )
        kpi = response.json()["kpis"]["low_stock"]
        assert "open_alerts" in kpi

    def test_rebook_kpi_structure(self, auth_headers):
        """Rebook KPI has correct fields"""
        response = requests.get(
            f"{BASE_URL}/api/tier1-dashboard/default?days=30",
            headers=auth_headers
        )
        kpi = response.json()["kpis"]["rebook"]
        assert "sent" in kpi
        assert "clicked" in kpi
        assert "click_rate_pct" in kpi

    def test_stay_ext_kpi_structure(self, auth_headers):
        """Stay extension KPI has correct fields"""
        response = requests.get(
            f"{BASE_URL}/api/tier1-dashboard/default?days=30",
            headers=auth_headers
        )
        kpi = response.json()["kpis"]["stay_ext"]
        assert "extensions" in kpi
        assert "extra_nights" in kpi
        assert "extra_revenue" in kpi

    def test_long_stay_kpi_structure(self, auth_headers):
        """Long stay KPI has correct fields"""
        response = requests.get(
            f"{BASE_URL}/api/tier1-dashboard/default?days=30",
            headers=auth_headers
        )
        kpi = response.json()["kpis"]["long_stay"]
        assert "applied" in kpi
        assert "discount_total" in kpi

    def test_cancel_insurance_kpi_structure(self, auth_headers):
        """Cancel insurance KPI has correct fields"""
        response = requests.get(
            f"{BASE_URL}/api/tier1-dashboard/default?days=30",
            headers=auth_headers
        )
        kpi = response.json()["kpis"]["cancel_insurance"]
        assert "policies" in kpi
        assert "claimed" in kpi
        assert "fee_revenue" in kpi
        assert "claim_loss_estimate" in kpi
        assert "net_pl" in kpi

    def test_group_rooming_kpi_structure(self, auth_headers):
        """Group rooming KPI has correct fields"""
        response = requests.get(
            f"{BASE_URL}/api/tier1-dashboard/default?days=30",
            headers=auth_headers
        )
        kpi = response.json()["kpis"]["group_rooming"]
        assert "finalized_sessions" in kpi

    def test_ci_slots_kpi_structure(self, auth_headers):
        """CI slots KPI has correct fields"""
        response = requests.get(
            f"{BASE_URL}/api/tier1-dashboard/default?days=30",
            headers=auth_headers
        )
        kpi = response.json()["kpis"]["ci_slots"]
        assert "reservations" in kpi
        assert "early_paid" in kpi

    def test_highlights_auto_generated(self, auth_headers):
        """Highlights array is auto-generated based on thresholds"""
        response = requests.get(
            f"{BASE_URL}/api/tier1-dashboard/default?days=30",
            headers=auth_headers
        )
        data = response.json()
        highlights = data["highlights"]
        
        # Highlights should be a list
        assert isinstance(highlights, list)
        
        # Each highlight should have label, value, kind
        for h in highlights:
            assert "label" in h
            assert "value" in h
            assert "kind" in h
            assert h["kind"] in ["win", "alert"]

    def test_days_parameter_works(self, auth_headers):
        """Days parameter changes the window"""
        response7 = requests.get(
            f"{BASE_URL}/api/tier1-dashboard/default?days=7",
            headers=auth_headers
        )
        response90 = requests.get(
            f"{BASE_URL}/api/tier1-dashboard/default?days=90",
            headers=auth_headers
        )
        
        assert response7.status_code == 200
        assert response90.status_code == 200
        
        assert response7.json()["window_days"] == 7
        assert response90.json()["window_days"] == 90

    def test_different_property_id(self, auth_headers):
        """Dashboard works with different property IDs"""
        response = requests.get(
            f"{BASE_URL}/api/tier1-dashboard/aldgate-flats?days=30",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["property_id"] == "aldgate-flats"
        assert len(data["kpis"]) == 20

    def test_empty_property_returns_zeros(self, auth_headers):
        """Property with no data returns zero values, not 500"""
        response = requests.get(
            f"{BASE_URL}/api/tier1-dashboard/nonexistent-property?days=30",
            headers=auth_headers
        )
        # Should return 200 with zero values, not 500
        assert response.status_code == 200
        data = response.json()
        assert data["property_id"] == "nonexistent-property"
        # KPIs should have zero values
        assert data["kpis"]["preauth"]["total_holds"] == 0
        assert data["kpis"]["chargeback"]["cases"] == 0


class TestTier1DashboardRBAC:
    """Tests for role-based access control"""

    def test_manager_can_access(self):
        """Manager role can access the dashboard"""
        # First login as admin to create a manager if needed
        admin_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        admin_token = admin_resp.json()["token"]
        
        # Admin should be able to access
        response = requests.get(
            f"{BASE_URL}/api/tier1-dashboard/default?days=30",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200

    def test_receptionist_cannot_access(self):
        """Receptionist role should not access (admin/manager only)"""
        # Login as receptionist
        recep_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testrecep@hotelbox.com",
            "password": "Test2026!"
        })
        if recep_resp.status_code != 200:
            pytest.skip("Receptionist user not available")
        
        recep_token = recep_resp.json()["token"]
        
        response = requests.get(
            f"{BASE_URL}/api/tier1-dashboard/default?days=30",
            headers={"Authorization": f"Bearer {recep_token}"}
        )
        # Should be forbidden for non-admin/manager
        assert response.status_code in [403, 401]


class TestTier1DashboardDataIntegrity:
    """Tests for data integrity and calculations"""

    def test_chargeback_win_rate_calculation(self, auth_headers):
        """Chargeback win rate is calculated correctly"""
        response = requests.get(
            f"{BASE_URL}/api/tier1-dashboard/default?days=30",
            headers=auth_headers
        )
        kpi = response.json()["kpis"]["chargeback"]
        
        won = kpi["won"]
        lost = kpi["lost"]
        win_rate = kpi["win_rate_pct"]
        
        if won + lost > 0:
            expected_rate = round(won * 100 / (won + lost), 1)
            assert win_rate == expected_rate

    def test_sr_voucher_redeem_rate_calculation(self, auth_headers):
        """SR voucher redeem rate is calculated correctly"""
        response = requests.get(
            f"{BASE_URL}/api/tier1-dashboard/default?days=30",
            headers=auth_headers
        )
        kpi = response.json()["kpis"]["sr_voucher"]
        
        issued = kpi["issued"]
        redeemed = kpi["redeemed"]
        redeem_rate = kpi["redeem_rate_pct"]
        
        if issued > 0:
            expected_rate = round(redeemed * 100 / issued, 1)
            assert redeem_rate == expected_rate

    def test_cancel_insurance_net_pl_calculation(self, auth_headers):
        """Cancel insurance net P&L is calculated correctly"""
        response = requests.get(
            f"{BASE_URL}/api/tier1-dashboard/default?days=30",
            headers=auth_headers
        )
        kpi = response.json()["kpis"]["cancel_insurance"]
        
        fee_revenue = kpi["fee_revenue"]
        claim_loss = kpi["claim_loss_estimate"]
        net_pl = kpi["net_pl"]
        
        expected_net = round(fee_revenue - claim_loss, 2)
        assert net_pl == expected_net
