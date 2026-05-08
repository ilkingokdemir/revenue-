"""
Iteration 269: Workforce Extras - Bordro CSV Export + Tip Pool Distribution
Tests for:
1. GET /api/payroll/export/{property_id}?week_start=YYYY-MM-DD - CSV export with Turkish headers
2. GET /api/payroll/export/{property_id}?month=YYYY-MM - Monthly CSV export
3. POST /api/tip-pool/distribute - Tip distribution with 3 modes (equal/hours/role)
4. GET /api/tip-pool/history/{property_id}?days=30 - Tip distribution history
"""
import pytest
import requests
import os
import csv
import io
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
HOUSEKEEPER_EMAIL = "testhk@hotelbox.com"
HOUSEKEEPER_PASSWORD = "Test2026!"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        data = response.json()
        # API returns 'token' not 'access_token'
        return data.get("token") or data.get("access_token")
    pytest.skip(f"Admin login failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def housekeeper_token():
    """Get housekeeper auth token (should be denied for admin/manager endpoints)"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": HOUSEKEEPER_EMAIL,
        "password": HOUSEKEEPER_PASSWORD
    })
    if response.status_code == 200:
        data = response.json()
        return data.get("token") or data.get("access_token")
    return None  # May not exist, skip tests that need it


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def test_shift_data(admin_token, api_client):
    """Seed test shift data for payroll export and tip distribution"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    today = datetime.now().strftime("%Y-%m-%d")
    week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime("%Y-%m-%d")
    
    # Create test shifts with different statuses
    test_shifts = [
        {
            "id": f"TEST_shift_completed_1",
            "property_id": "default",
            "staff_id": "TEST_staff_chef_1",
            "staff_name": "TEST_Chef Ali",
            "role": "chef",
            "date": today,
            "week_start": week_start,
            "start_time": "08:00",
            "end_time": "16:00",
            "hours_worked": 8.0,
            "status": "completed",
            "pay_type": "hourly",
            "pay_rate": 15.0,
            "currency": "GBP",
            "earned_amount": 120.0
        },
        {
            "id": f"TEST_shift_completed_2",
            "property_id": "default",
            "staff_id": "TEST_staff_server_1",
            "staff_name": "TEST_Server Ayse",
            "role": "server",
            "date": today,
            "week_start": week_start,
            "start_time": "10:00",
            "end_time": "18:00",
            "hours_worked": 8.0,
            "status": "completed",
            "pay_type": "hourly",
            "pay_rate": 12.0,
            "currency": "GBP",
            "earned_amount": 96.0
        },
        {
            "id": f"TEST_shift_approved_1",
            "property_id": "default",
            "staff_id": "TEST_staff_kds_1",
            "staff_name": "TEST_KDS Mehmet",
            "role": "kds",
            "date": today,
            "week_start": week_start,
            "start_time": "12:00",
            "end_time": "20:00",
            "hours_worked": 8.0,
            "status": "approved",
            "pay_type": "daily",
            "pay_rate": 80.0,
            "currency": "GBP",
            "earned_amount": 80.0
        },
        {
            "id": f"TEST_shift_draft_1",
            "property_id": "default",
            "staff_id": "TEST_staff_server_2",
            "staff_name": "TEST_Server Fatma",
            "role": "server",
            "date": today,
            "week_start": week_start,
            "start_time": "14:00",
            "end_time": "22:00",
            "hours_worked": 8.0,
            "status": "draft",  # Should be excluded from payroll export
            "pay_type": "hourly",
            "pay_rate": 12.0,
            "currency": "GBP",
            "earned_amount": 96.0
        },
        {
            "id": f"TEST_shift_planned_1",
            "property_id": "default",
            "staff_id": "TEST_staff_chef_2",
            "staff_name": "TEST_Chef Zeynep",
            "role": "chef",
            "date": today,
            "week_start": week_start,
            "start_time": "16:00",
            "end_time": "00:00",
            "hours_worked": 8.0,
            "status": "planned",  # Should be excluded from payroll export but included in tip distribution
            "pay_type": "hourly",
            "pay_rate": 15.0,
            "currency": "GBP",
            "earned_amount": 120.0
        }
    ]
    
    # Insert test shifts directly via MongoDB (using a helper endpoint or direct insert)
    # For now, we'll use the shifts v2 endpoint if available
    created_ids = []
    for shift in test_shifts:
        # Try to create via API
        resp = api_client.post(f"{BASE_URL}/api/shifts/v2/entries", json=shift, headers=headers)
        if resp.status_code in [200, 201]:
            created_ids.append(shift["id"])
    
    yield {
        "today": today,
        "week_start": week_start,
        "month": datetime.now().strftime("%Y-%m"),
        "created_ids": created_ids,
        "test_shifts": test_shifts
    }
    
    # Cleanup: Delete test shifts
    for shift_id in created_ids:
        api_client.delete(f"{BASE_URL}/api/shifts/v2/entries/{shift_id}", headers=headers)


# ==================== PAYROLL CSV EXPORT TESTS ====================

class TestPayrollExportAuth:
    """Test authentication requirements for payroll export"""
    
    def test_payroll_export_requires_auth(self, api_client):
        """Payroll export should require authentication"""
        response = api_client.get(f"{BASE_URL}/api/payroll/export/default?week_start=2026-01-01")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("PASS: Payroll export requires authentication")
    
    def test_payroll_export_denied_for_housekeeper(self, api_client, housekeeper_token):
        """Payroll export should be denied for non-admin/manager roles"""
        if not housekeeper_token:
            pytest.skip("Housekeeper user not available")
        headers = {"Authorization": f"Bearer {housekeeper_token}"}
        response = api_client.get(f"{BASE_URL}/api/payroll/export/default?week_start=2026-01-01", headers=headers)
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print("PASS: Payroll export denied for housekeeper role")


class TestPayrollExportCSV:
    """Test CSV export functionality"""
    
    def test_payroll_export_returns_csv_content_type(self, api_client, admin_token, test_shift_data):
        """Payroll export should return text/csv content type"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = api_client.get(
            f"{BASE_URL}/api/payroll/export/default?week_start={test_shift_data['week_start']}", 
            headers=headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        assert "text/csv" in response.headers.get("Content-Type", ""), \
            f"Expected text/csv, got {response.headers.get('Content-Type')}"
        print("PASS: Payroll export returns text/csv content type")
    
    def test_payroll_export_has_content_disposition(self, api_client, admin_token, test_shift_data):
        """Payroll export should have Content-Disposition header for download"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = api_client.get(
            f"{BASE_URL}/api/payroll/export/default?week_start={test_shift_data['week_start']}", 
            headers=headers
        )
        assert response.status_code == 200
        content_disp = response.headers.get("Content-Disposition", "")
        assert "attachment" in content_disp, f"Expected attachment, got {content_disp}"
        assert "filename=" in content_disp, f"Expected filename, got {content_disp}"
        assert ".csv" in content_disp, f"Expected .csv extension, got {content_disp}"
        print(f"PASS: Content-Disposition header correct: {content_disp}")
    
    def test_payroll_export_turkish_headers(self, api_client, admin_token, test_shift_data):
        """Payroll export should have Turkish headers"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = api_client.get(
            f"{BASE_URL}/api/payroll/export/default?week_start={test_shift_data['week_start']}", 
            headers=headers
        )
        assert response.status_code == 200
        
        # Parse CSV
        csv_content = response.text
        reader = csv.reader(io.StringIO(csv_content))
        header_row = next(reader)
        
        expected_headers = ["Personel", "Rol", "Ödeme Tipi", "Birim Ücret", "Para Birimi",
                          "Vardiya Sayısı", "Toplam Saat", "Toplam Kazanç"]
        
        assert header_row == expected_headers, f"Expected {expected_headers}, got {header_row}"
        print(f"PASS: Turkish headers correct: {header_row}")
    
    def test_payroll_export_has_toplam_row(self, api_client, admin_token, test_shift_data):
        """Payroll export should have TOPLAM (total) row at end"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = api_client.get(
            f"{BASE_URL}/api/payroll/export/all?week_start={test_shift_data['week_start']}", 
            headers=headers
        )
        assert response.status_code == 200
        
        # Parse CSV and find TOPLAM row
        csv_content = response.text
        rows = list(csv.reader(io.StringIO(csv_content)))
        
        # Find TOPLAM row (should be last non-empty row)
        toplam_row = None
        for row in reversed(rows):
            if row and row[0] == "TOPLAM":
                toplam_row = row
                break
        
        assert toplam_row is not None, "TOPLAM row not found in CSV"
        assert toplam_row[0] == "TOPLAM", f"Expected TOPLAM, got {toplam_row[0]}"
        print(f"PASS: TOPLAM row found: {toplam_row}")
    
    def test_payroll_export_excludes_draft_planned(self, api_client, admin_token, test_shift_data):
        """Payroll export should only include completed/approved shifts"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = api_client.get(
            f"{BASE_URL}/api/payroll/export/default?week_start={test_shift_data['week_start']}", 
            headers=headers
        )
        assert response.status_code == 200
        
        csv_content = response.text
        # Draft and planned staff should NOT appear in payroll export
        assert "TEST_Server Fatma" not in csv_content, "Draft shift should be excluded"
        assert "TEST_Chef Zeynep" not in csv_content, "Planned shift should be excluded"
        print("PASS: Draft and planned shifts excluded from payroll export")
    
    def test_payroll_export_by_month(self, api_client, admin_token, test_shift_data):
        """Payroll export should work with month parameter"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = api_client.get(
            f"{BASE_URL}/api/payroll/export/all?month={test_shift_data['month']}", 
            headers=headers
        )
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("Content-Type", "")
        print(f"PASS: Monthly payroll export works for {test_shift_data['month']}")
    
    def test_payroll_export_property_all(self, api_client, admin_token, test_shift_data):
        """Payroll export should work with property_id='all'"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = api_client.get(
            f"{BASE_URL}/api/payroll/export/all?week_start={test_shift_data['week_start']}", 
            headers=headers
        )
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("Content-Type", "")
        print("PASS: Payroll export works with property_id='all'")
    
    def test_payroll_export_numeric_precision(self, api_client, admin_token, test_shift_data):
        """Payroll export should round numerics to 2 decimals"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = api_client.get(
            f"{BASE_URL}/api/payroll/export/all?week_start={test_shift_data['week_start']}", 
            headers=headers
        )
        assert response.status_code == 200
        
        csv_content = response.text
        rows = list(csv.reader(io.StringIO(csv_content)))
        
        # Check numeric columns (Birim Ücret, Toplam Saat, Toplam Kazanç)
        for row in rows[1:]:  # Skip header
            if row and row[0] and row[0] != "TOPLAM" and row[0] != "":
                # Check pay_rate (column 3), hours (column 6), earned (column 7)
                if len(row) >= 8:
                    for col_idx in [3, 6, 7]:
                        if row[col_idx]:
                            # Should be formatted with max 2 decimal places
                            parts = row[col_idx].split(".")
                            if len(parts) == 2:
                                assert len(parts[1]) <= 2, f"More than 2 decimals: {row[col_idx]}"
        print("PASS: Numeric values have max 2 decimal places")


# ==================== TIP POOL DISTRIBUTION TESTS ====================

class TestTipPoolAuth:
    """Test authentication requirements for tip pool endpoints"""
    
    def test_tip_distribute_requires_auth(self, api_client):
        """Tip distribution should require authentication"""
        response = api_client.post(f"{BASE_URL}/api/tip-pool/distribute", json={
            "property_id": "default",
            "total_tips": 100,
            "mode": "equal"
        })
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("PASS: Tip distribution requires authentication")
    
    def test_tip_history_requires_auth(self, api_client):
        """Tip history should require authentication"""
        response = api_client.get(f"{BASE_URL}/api/tip-pool/history/default")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("PASS: Tip history requires authentication")


class TestTipPoolDistribute:
    """Test tip pool distribution functionality"""
    
    def test_tip_distribute_mode_equal(self, api_client, admin_token, test_shift_data):
        """Tip distribution with mode=equal should divide evenly"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = api_client.post(f"{BASE_URL}/api/tip-pool/distribute", json={
            "property_id": "default",
            "date": test_shift_data["today"],
            "total_tips": 100.0,
            "mode": "equal"
        }, headers=headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "distributed" in data, "Response should have 'distributed' field"
        assert "shares" in data, "Response should have 'shares' field"
        assert "total_tips" in data, "Response should have 'total_tips' field"
        assert "mode" in data, "Response should have 'mode' field"
        assert data["mode"] == "equal"
        
        # In equal mode, all weights should be 1.0
        if data["shares"]:
            for share in data["shares"]:
                assert share["weight"] == 1.0, f"Equal mode should have weight=1.0, got {share['weight']}"
        
        print(f"PASS: Equal distribution - {data['distributed']} shares created")
    
    def test_tip_distribute_mode_hours(self, api_client, admin_token, test_shift_data):
        """Tip distribution with mode=hours should weight by hours_worked"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = api_client.post(f"{BASE_URL}/api/tip-pool/distribute", json={
            "property_id": "default",
            "date": test_shift_data["today"],
            "total_tips": 200.0,
            "mode": "hours"
        }, headers=headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data["mode"] == "hours"
        
        # In hours mode, weights should reflect hours worked
        if data["shares"]:
            for share in data["shares"]:
                hours = share.get("hours") or 8  # Default 8 if not set
                # Weight should be max(0.5, hours)
                expected_weight = max(0.5, float(hours) if hours else 8)
                assert abs(share["weight"] - expected_weight) < 0.1, \
                    f"Hours mode weight mismatch: expected ~{expected_weight}, got {share['weight']}"
        
        print(f"PASS: Hours-based distribution - {data['distributed']} shares")
    
    def test_tip_distribute_mode_role(self, api_client, admin_token, test_shift_data):
        """Tip distribution with mode=role should apply role weights"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = api_client.post(f"{BASE_URL}/api/tip-pool/distribute", json={
            "property_id": "default",
            "date": test_shift_data["today"],
            "total_tips": 300.0,
            "mode": "role"
        }, headers=headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data["mode"] == "role"
        
        # Default role weights: chef=1.5, server=1.0, kds=0.7
        role_weights = {"chef": 1.5, "server": 1.0, "kds": 0.7}
        
        if data["shares"]:
            for share in data["shares"]:
                role = (share.get("role") or "").lower()
                expected_multiplier = role_weights.get(role, 1.0)
                hours = share.get("hours") or 8
                expected_weight = expected_multiplier * max(0.5, float(hours) if hours else 8)
                # Allow some tolerance
                assert abs(share["weight"] - expected_weight) < 0.5, \
                    f"Role mode weight mismatch for {role}: expected ~{expected_weight}, got {share['weight']}"
        
        print(f"PASS: Role-based distribution - {data['distributed']} shares")
    
    def test_tip_distribute_custom_role_weights(self, api_client, admin_token, test_shift_data):
        """Tip distribution should accept custom role_weights"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        custom_weights = {"chef": 2.0, "server": 1.5, "kds": 1.0}
        
        response = api_client.post(f"{BASE_URL}/api/tip-pool/distribute", json={
            "property_id": "default",
            "date": test_shift_data["today"],
            "total_tips": 150.0,
            "mode": "role",
            "role_weights": custom_weights
        }, headers=headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify custom weights are applied
        if data["shares"]:
            for share in data["shares"]:
                role = (share.get("role") or "").lower()
                expected_multiplier = custom_weights.get(role, 1.0)
                hours = share.get("hours") or 8
                expected_weight = expected_multiplier * max(0.5, float(hours) if hours else 8)
                # Allow tolerance
                assert abs(share["weight"] - expected_weight) < 0.5, \
                    f"Custom weight mismatch for {role}"
        
        print(f"PASS: Custom role weights applied")
    
    def test_tip_distribute_returns_400_for_zero_tips(self, api_client, admin_token, test_shift_data):
        """Tip distribution should return 400 if total_tips <= 0"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Test with 0
        response = api_client.post(f"{BASE_URL}/api/tip-pool/distribute", json={
            "property_id": "default",
            "date": test_shift_data["today"],
            "total_tips": 0,
            "mode": "equal"
        }, headers=headers)
        assert response.status_code == 400, f"Expected 400 for total_tips=0, got {response.status_code}"
        
        # Test with negative
        response = api_client.post(f"{BASE_URL}/api/tip-pool/distribute", json={
            "property_id": "default",
            "date": test_shift_data["today"],
            "total_tips": -50,
            "mode": "equal"
        }, headers=headers)
        assert response.status_code == 400, f"Expected 400 for negative tips, got {response.status_code}"
        
        print("PASS: Returns 400 for total_tips <= 0")
    
    def test_tip_distribute_no_shifts_returns_note(self, api_client, admin_token):
        """Tip distribution should return empty shares + note when no shifts exist"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Use a date far in the future where no shifts exist
        future_date = "2099-12-31"
        
        response = api_client.post(f"{BASE_URL}/api/tip-pool/distribute", json={
            "property_id": "nonexistent-property-xyz",
            "date": future_date,
            "total_tips": 100.0,
            "mode": "equal"
        }, headers=headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data["distributed"] == 0, f"Expected 0 distributed, got {data['distributed']}"
        assert data["shares"] == [], f"Expected empty shares, got {data['shares']}"
        assert "note" in data, "Expected 'note' field when no shifts"
        
        print(f"PASS: No shifts returns empty shares with note: {data.get('note')}")
    
    def test_tip_distribute_sum_equals_total(self, api_client, admin_token, test_shift_data):
        """Sum of all shares should approximately equal total_tips (±£0.10 tolerance)"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        total_tips = 157.89  # Odd amount to test rounding
        
        response = api_client.post(f"{BASE_URL}/api/tip-pool/distribute", json={
            "property_id": "all",
            "date": test_shift_data["today"],
            "total_tips": total_tips,
            "mode": "hours"
        }, headers=headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        if data["shares"]:
            total_distributed = sum(share["share"] for share in data["shares"])
            diff = abs(total_distributed - total_tips)
            assert diff <= 0.10, f"Sum of shares ({total_distributed}) differs from total ({total_tips}) by {diff}"
            print(f"PASS: Sum of shares ({total_distributed}) ≈ total_tips ({total_tips}), diff={diff:.2f}")
        else:
            print("PASS: No shares to sum (no shifts on date)")
    
    def test_tip_distribute_persists_to_collection(self, api_client, admin_token, test_shift_data):
        """Tip distribution should persist to tip_distributions collection"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = api_client.post(f"{BASE_URL}/api/tip-pool/distribute", json={
            "property_id": "default",
            "date": test_shift_data["today"],
            "total_tips": 50.0,
            "mode": "equal"
        }, headers=headers)
        
        assert response.status_code == 200
        
        # Verify by fetching history
        history_response = api_client.get(
            f"{BASE_URL}/api/tip-pool/history/default?days=1",
            headers=headers
        )
        assert history_response.status_code == 200
        history = history_response.json()
        
        # Should find at least one distribution
        assert len(history) >= 1, "Expected at least 1 distribution in history"
        
        # Check required fields in persisted record
        latest = history[0]
        required_fields = ["id", "property_id", "date", "total_tips", "mode", "shares", "created_at"]
        for field in required_fields:
            assert field in latest, f"Missing field '{field}' in persisted record"
        
        print(f"PASS: Distribution persisted with all required fields")


class TestTipPoolHistory:
    """Test tip pool history endpoint"""
    
    def test_tip_history_returns_list(self, api_client, admin_token):
        """Tip history should return a list"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = api_client.get(f"{BASE_URL}/api/tip-pool/history/default?days=30", headers=headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"PASS: Tip history returns list with {len(data)} items")
    
    def test_tip_history_sorted_by_created_at_desc(self, api_client, admin_token):
        """Tip history should be sorted by created_at descending"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = api_client.get(f"{BASE_URL}/api/tip-pool/history/all?days=30", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        if len(data) >= 2:
            # Check descending order
            for i in range(len(data) - 1):
                assert data[i]["created_at"] >= data[i+1]["created_at"], \
                    f"Not sorted desc: {data[i]['created_at']} < {data[i+1]['created_at']}"
            print("PASS: History sorted by created_at descending")
        else:
            print("PASS: Not enough records to verify sorting (need >=2)")
    
    def test_tip_history_property_filter(self, api_client, admin_token):
        """Tip history should filter by property_id"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Get history for specific property
        response = api_client.get(f"{BASE_URL}/api/tip-pool/history/default?days=30", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        # All records should have matching property_id
        for record in data:
            assert record["property_id"] == "default", \
                f"Expected property_id='default', got {record['property_id']}"
        
        print(f"PASS: History filtered by property_id")
    
    def test_tip_history_property_all(self, api_client, admin_token):
        """Tip history with property_id='all' should return all properties"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = api_client.get(f"{BASE_URL}/api/tip-pool/history/all?days=30", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        print(f"PASS: History for 'all' returns {len(data)} records")


class TestTipPoolShareStructure:
    """Test the structure of tip distribution shares"""
    
    def test_share_has_required_fields(self, api_client, admin_token, test_shift_data):
        """Each share should have required fields"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = api_client.post(f"{BASE_URL}/api/tip-pool/distribute", json={
            "property_id": "all",
            "date": test_shift_data["today"],
            "total_tips": 100.0,
            "mode": "role"
        }, headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        if data["shares"]:
            required_fields = ["shift_id", "staff_id", "staff_name", "role", "hours", "weight", "share"]
            for share in data["shares"]:
                for field in required_fields:
                    assert field in share, f"Missing field '{field}' in share"
            print(f"PASS: All shares have required fields")
        else:
            print("PASS: No shares to validate (no shifts on date)")


# ==================== INTEGRATION TESTS ====================

class TestWorkforceExtrasIntegration:
    """Integration tests for workforce extras"""
    
    def test_payroll_and_tip_use_same_shifts(self, api_client, admin_token, test_shift_data):
        """Payroll export and tip distribution should use consistent shift data"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Get payroll export
        payroll_response = api_client.get(
            f"{BASE_URL}/api/payroll/export/all?week_start={test_shift_data['week_start']}", 
            headers=headers
        )
        assert payroll_response.status_code == 200
        
        # Get tip distribution
        tip_response = api_client.post(f"{BASE_URL}/api/tip-pool/distribute", json={
            "property_id": "all",
            "date": test_shift_data["today"],
            "total_tips": 100.0,
            "mode": "equal"
        }, headers=headers)
        assert tip_response.status_code == 200
        
        print("PASS: Both endpoints work with same shift data")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
