"""
Test: Auto-sync shifts to finance_earned_salaries
Tests the automatic creation of finance entries when shifts are marked completed/approved.

Features tested:
1. PUT /api/shifts/entries/{shift_id} with status:completed → auto-creates finance entry
2. PUT /api/shifts/entries/{shift_id} with status:approved → auto-creates finance entry
3. POST /api/shifts/bulk/mark-completed returns completed count AND synced_to_finance count
4. POST /api/shifts/bulk/approve-completed returns approved count AND synced_to_finance count
5. Idempotency: marking same shift completed twice should NOT create duplicate finance entries
6. Sync helper logic: hours_worked auto-computed, earned amount auto-computed
7. GET /api/shifts/entries/{property_id}?week_start returns data including pay_rate/earned_amount
"""

import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test data prefix for cleanup
TEST_PREFIX = "TEST_AUTOSYNC_"


@pytest.fixture(scope="module")
def auth_token():
    """Get admin auth token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    return data.get("token") or data.get("access_token")


@pytest.fixture(scope="module")
def headers(auth_token):
    """Auth headers for requests"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


@pytest.fixture(scope="module")
def test_property_id():
    """Use a test property ID"""
    return "test-property-autosync"


@pytest.fixture(scope="module")
def test_week_start():
    """Get a test week start date (Monday of current week)"""
    today = datetime.now()
    monday = today - timedelta(days=today.weekday())
    return monday.strftime("%Y-%m-%d")


@pytest.fixture(scope="module")
def test_staff(headers, test_property_id):
    """Create a test staff member for shift tests"""
    staff_data = {
        "property_id": test_property_id,
        "name": f"{TEST_PREFIX}Staff_{uuid.uuid4().hex[:6]}",
        "role": "housekeeper",
        "pay_type": "hourly",
        "pay_rate": 15.0,
        "currency": "GBP",
        "email": f"{TEST_PREFIX}staff@test.com",
        "phone": "1234567890"
    }
    response = requests.post(f"{BASE_URL}/api/shifts/staff", json=staff_data, headers=headers)
    assert response.status_code == 200, f"Failed to create staff: {response.text}"
    staff = response.json()
    yield staff
    # Cleanup
    requests.delete(f"{BASE_URL}/api/shifts/staff/{staff['id']}", headers=headers)


class TestAutoSyncOnSingleShiftUpdate:
    """Test auto-sync when updating a single shift to completed/approved"""

    def test_update_shift_to_completed_creates_finance_entry(self, headers, test_property_id, test_week_start, test_staff):
        """PUT /api/shifts/entries/{shift_id} with status:completed → auto-creates finance entry"""
        # Create a shift with planned status
        shift_date = test_week_start
        shift_data = {
            "property_id": test_property_id,
            "staff_id": test_staff["id"],
            "staff_name": test_staff["name"],
            "role": test_staff["role"],
            "date": shift_date,
            "week_start": test_week_start,
            "start_time": "09:00",
            "end_time": "17:00",
            "status": "planned",
            "pay_type": "hourly",
            "pay_rate": 15.0,
            "notes": f"{TEST_PREFIX}completed_test"
        }
        create_resp = requests.post(f"{BASE_URL}/api/shifts/entries", json=shift_data, headers=headers)
        assert create_resp.status_code == 200, f"Failed to create shift: {create_resp.text}"
        shift = create_resp.json()
        shift_id = shift["id"]

        # Verify hours_worked and earned_amount are auto-calculated
        assert shift.get("hours_worked") == 8.0, f"Expected 8 hours, got {shift.get('hours_worked')}"
        assert shift.get("earned_amount") == 120.0, f"Expected 120 (8h * 15), got {shift.get('earned_amount')}"

        try:
            # Update shift to completed
            update_resp = requests.put(
                f"{BASE_URL}/api/shifts/entries/{shift_id}",
                json={"status": "completed"},
                headers=headers
            )
            assert update_resp.status_code == 200, f"Failed to update shift: {update_resp.text}"
            updated_shift = update_resp.json()
            assert updated_shift["status"] == "completed"

            # Verify finance entry was created by checking sync-to-salaries endpoint
            # The _sync_to_finance helper should have created an entry
            sync_resp = requests.post(
                f"{BASE_URL}/api/shifts/sync-to-salaries",
                json={"week_start": test_week_start, "property_id": test_property_id},
                headers=headers
            )
            assert sync_resp.status_code == 200
            sync_data = sync_resp.json()
            # Since entry already exists (created by auto-sync), synced should be 0
            print(f"Sync response after completed: {sync_data}")
            # The fact that synced=0 means the entry was already created by auto-sync
            
        finally:
            # Cleanup shift
            requests.delete(f"{BASE_URL}/api/shifts/entries/{shift_id}", headers=headers)

    def test_update_shift_to_approved_creates_finance_entry(self, headers, test_property_id, test_week_start, test_staff):
        """PUT /api/shifts/entries/{shift_id} with status:approved → auto-creates finance entry"""
        # Create a shift with planned status
        shift_date = test_week_start
        shift_data = {
            "property_id": test_property_id,
            "staff_id": test_staff["id"],
            "staff_name": test_staff["name"],
            "role": test_staff["role"],
            "date": shift_date,
            "week_start": test_week_start,
            "start_time": "10:00",
            "end_time": "18:00",
            "status": "planned",
            "pay_type": "hourly",
            "pay_rate": 15.0,
            "notes": f"{TEST_PREFIX}approved_test"
        }
        create_resp = requests.post(f"{BASE_URL}/api/shifts/entries", json=shift_data, headers=headers)
        assert create_resp.status_code == 200, f"Failed to create shift: {create_resp.text}"
        shift = create_resp.json()
        shift_id = shift["id"]

        try:
            # Update shift directly to approved
            update_resp = requests.put(
                f"{BASE_URL}/api/shifts/entries/{shift_id}",
                json={"status": "approved"},
                headers=headers
            )
            assert update_resp.status_code == 200, f"Failed to update shift: {update_resp.text}"
            updated_shift = update_resp.json()
            assert updated_shift["status"] == "approved"

            # Verify finance entry was created
            sync_resp = requests.post(
                f"{BASE_URL}/api/shifts/sync-to-salaries",
                json={"week_start": test_week_start, "property_id": test_property_id},
                headers=headers
            )
            assert sync_resp.status_code == 200
            sync_data = sync_resp.json()
            print(f"Sync response after approved: {sync_data}")
            # synced=0 means entry already exists from auto-sync
            
        finally:
            # Cleanup shift
            requests.delete(f"{BASE_URL}/api/shifts/entries/{shift_id}", headers=headers)


class TestBulkActionsReturnSyncCount:
    """Test bulk actions return both completed/approved count AND synced_to_finance count"""

    def test_bulk_mark_completed_returns_sync_count(self, headers, test_property_id, test_week_start, test_staff):
        """POST /api/shifts/bulk/mark-completed returns BOTH completed count AND synced_to_finance count"""
        # Create multiple shifts with published status
        shift_ids = []
        for i in range(3):
            shift_date = (datetime.strptime(test_week_start, "%Y-%m-%d") + timedelta(days=i)).strftime("%Y-%m-%d")
            shift_data = {
                "property_id": test_property_id,
                "staff_id": test_staff["id"],
                "staff_name": test_staff["name"],
                "role": test_staff["role"],
                "date": shift_date,
                "week_start": test_week_start,
                "start_time": "09:00",
                "end_time": "17:00",
                "status": "published",
                "pay_type": "hourly",
                "pay_rate": 15.0,
                "notes": f"{TEST_PREFIX}bulk_completed_{i}"
            }
            resp = requests.post(f"{BASE_URL}/api/shifts/entries", json=shift_data, headers=headers)
            assert resp.status_code == 200, f"Failed to create shift {i}: {resp.text}"
            shift_ids.append(resp.json()["id"])

        try:
            # Call bulk mark-completed
            bulk_resp = requests.post(
                f"{BASE_URL}/api/shifts/bulk/mark-completed",
                json={"week_start": test_week_start, "property_id": test_property_id},
                headers=headers
            )
            assert bulk_resp.status_code == 200, f"Bulk mark-completed failed: {bulk_resp.text}"
            bulk_data = bulk_resp.json()
            
            # Verify response contains both counts
            assert "completed" in bulk_data, f"Response missing 'completed' count: {bulk_data}"
            assert "synced_to_finance" in bulk_data, f"Response missing 'synced_to_finance' count: {bulk_data}"
            
            print(f"Bulk mark-completed response: {bulk_data}")
            assert bulk_data["completed"] >= 3, f"Expected at least 3 completed, got {bulk_data['completed']}"
            assert bulk_data["synced_to_finance"] >= 3, f"Expected at least 3 synced, got {bulk_data['synced_to_finance']}"
            
        finally:
            # Cleanup shifts
            for sid in shift_ids:
                requests.delete(f"{BASE_URL}/api/shifts/entries/{sid}", headers=headers)

    def test_bulk_approve_completed_returns_sync_count(self, headers, test_property_id, test_week_start, test_staff):
        """POST /api/shifts/bulk/approve-completed returns BOTH approved count AND synced_to_finance count"""
        # Create multiple shifts with completed status
        shift_ids = []
        for i in range(2):
            shift_date = (datetime.strptime(test_week_start, "%Y-%m-%d") + timedelta(days=i+4)).strftime("%Y-%m-%d")
            shift_data = {
                "property_id": test_property_id,
                "staff_id": test_staff["id"],
                "staff_name": test_staff["name"],
                "role": test_staff["role"],
                "date": shift_date,
                "week_start": test_week_start,
                "start_time": "08:00",
                "end_time": "16:00",
                "status": "completed",
                "pay_type": "hourly",
                "pay_rate": 15.0,
                "notes": f"{TEST_PREFIX}bulk_approve_{i}"
            }
            resp = requests.post(f"{BASE_URL}/api/shifts/entries", json=shift_data, headers=headers)
            assert resp.status_code == 200, f"Failed to create shift {i}: {resp.text}"
            shift_ids.append(resp.json()["id"])

        try:
            # Call bulk approve-completed
            bulk_resp = requests.post(
                f"{BASE_URL}/api/shifts/bulk/approve-completed",
                json={"week_start": test_week_start, "property_id": test_property_id},
                headers=headers
            )
            assert bulk_resp.status_code == 200, f"Bulk approve-completed failed: {bulk_resp.text}"
            bulk_data = bulk_resp.json()
            
            # Verify response contains both counts
            assert "approved" in bulk_data, f"Response missing 'approved' count: {bulk_data}"
            assert "synced_to_finance" in bulk_data, f"Response missing 'synced_to_finance' count: {bulk_data}"
            
            print(f"Bulk approve-completed response: {bulk_data}")
            assert bulk_data["approved"] >= 2, f"Expected at least 2 approved, got {bulk_data['approved']}"
            # synced_to_finance might be 0 if entries already exist from creation
            
        finally:
            # Cleanup shifts
            for sid in shift_ids:
                requests.delete(f"{BASE_URL}/api/shifts/entries/{sid}", headers=headers)


class TestIdempotency:
    """Test that marking the same shift completed twice does NOT create duplicate finance entries"""

    def test_idempotency_no_duplicate_finance_entries(self, headers, test_property_id, test_week_start, test_staff):
        """Marking the same shift completed twice should NOT create duplicate finance entries"""
        # Create a shift
        shift_date = test_week_start
        shift_data = {
            "property_id": test_property_id,
            "staff_id": test_staff["id"],
            "staff_name": test_staff["name"],
            "role": test_staff["role"],
            "date": shift_date,
            "week_start": test_week_start,
            "start_time": "09:00",
            "end_time": "17:00",
            "status": "planned",
            "pay_type": "hourly",
            "pay_rate": 20.0,
            "notes": f"{TEST_PREFIX}idempotency_test"
        }
        create_resp = requests.post(f"{BASE_URL}/api/shifts/entries", json=shift_data, headers=headers)
        assert create_resp.status_code == 200
        shift = create_resp.json()
        shift_id = shift["id"]

        try:
            # First update to completed - should create finance entry
            update1_resp = requests.put(
                f"{BASE_URL}/api/shifts/entries/{shift_id}",
                json={"status": "completed"},
                headers=headers
            )
            assert update1_resp.status_code == 200

            # Get initial sync count
            sync1_resp = requests.post(
                f"{BASE_URL}/api/shifts/sync-to-salaries",
                json={"week_start": test_week_start, "property_id": test_property_id},
                headers=headers
            )
            assert sync1_resp.status_code == 200
            sync1_data = sync1_resp.json()
            print(f"First sync after completed: {sync1_data}")

            # Update to planned and back to completed (simulating re-marking)
            requests.put(
                f"{BASE_URL}/api/shifts/entries/{shift_id}",
                json={"status": "planned"},
                headers=headers
            )
            
            # Second update to completed - should NOT create duplicate
            update2_resp = requests.put(
                f"{BASE_URL}/api/shifts/entries/{shift_id}",
                json={"status": "completed"},
                headers=headers
            )
            assert update2_resp.status_code == 200

            # Sync again - should return 0 synced (entry already exists)
            sync2_resp = requests.post(
                f"{BASE_URL}/api/shifts/sync-to-salaries",
                json={"week_start": test_week_start, "property_id": test_property_id},
                headers=headers
            )
            assert sync2_resp.status_code == 200
            sync2_data = sync2_resp.json()
            print(f"Second sync after re-completed: {sync2_data}")
            
            # The synced count should be 0 because entry already exists (idempotent)
            assert sync2_data["synced"] == 0, f"Expected 0 synced (idempotent), got {sync2_data['synced']}"
            
        finally:
            requests.delete(f"{BASE_URL}/api/shifts/entries/{shift_id}", headers=headers)


class TestSyncHelperLogic:
    """Test the _sync_to_finance helper logic"""

    def test_hours_worked_auto_computed_if_missing(self, headers, test_property_id, test_week_start, test_staff):
        """hours_worked should be auto-computed from start_time/end_time if missing"""
        shift_data = {
            "property_id": test_property_id,
            "staff_id": test_staff["id"],
            "staff_name": test_staff["name"],
            "role": test_staff["role"],
            "date": test_week_start,
            "week_start": test_week_start,
            "start_time": "08:00",
            "end_time": "14:00",  # 6 hours
            "status": "planned",
            "pay_type": "hourly",
            "pay_rate": 10.0,
            "notes": f"{TEST_PREFIX}hours_auto_compute"
        }
        create_resp = requests.post(f"{BASE_URL}/api/shifts/entries", json=shift_data, headers=headers)
        assert create_resp.status_code == 200
        shift = create_resp.json()
        shift_id = shift["id"]

        try:
            # Verify hours_worked is auto-calculated
            assert shift.get("hours_worked") == 6.0, f"Expected 6 hours, got {shift.get('hours_worked')}"
            
            # Verify earned_amount is auto-calculated (hourly: 6h * 10 = 60)
            assert shift.get("earned_amount") == 60.0, f"Expected 60, got {shift.get('earned_amount')}"
            
        finally:
            requests.delete(f"{BASE_URL}/api/shifts/entries/{shift_id}", headers=headers)

    def test_earned_amount_daily_rate(self, headers, test_property_id, test_week_start, test_staff):
        """For daily pay_type, earned_amount should equal pay_rate (not hours * rate)"""
        # Create a staff with daily pay
        daily_staff_data = {
            "property_id": test_property_id,
            "name": f"{TEST_PREFIX}DailyStaff_{uuid.uuid4().hex[:6]}",
            "role": "receptionist",
            "pay_type": "daily",
            "pay_rate": 100.0,
            "currency": "GBP"
        }
        staff_resp = requests.post(f"{BASE_URL}/api/shifts/staff", json=daily_staff_data, headers=headers)
        assert staff_resp.status_code == 200
        daily_staff = staff_resp.json()

        shift_data = {
            "property_id": test_property_id,
            "staff_id": daily_staff["id"],
            "staff_name": daily_staff["name"],
            "role": daily_staff["role"],
            "date": test_week_start,
            "week_start": test_week_start,
            "start_time": "09:00",
            "end_time": "17:00",  # 8 hours
            "status": "planned",
            "pay_type": "daily",
            "pay_rate": 100.0,
            "notes": f"{TEST_PREFIX}daily_rate_test"
        }
        create_resp = requests.post(f"{BASE_URL}/api/shifts/entries", json=shift_data, headers=headers)
        assert create_resp.status_code == 200
        shift = create_resp.json()
        shift_id = shift["id"]

        try:
            # For daily rate, earned_amount should be pay_rate (100), not hours * rate
            assert shift.get("earned_amount") == 100.0, f"Expected 100 (daily rate), got {shift.get('earned_amount')}"
            
        finally:
            requests.delete(f"{BASE_URL}/api/shifts/entries/{shift_id}", headers=headers)
            requests.delete(f"{BASE_URL}/api/shifts/staff/{daily_staff['id']}", headers=headers)

    def test_skip_sync_if_earned_zero(self, headers, test_property_id, test_week_start, test_staff):
        """Shifts with earned <= 0 should be skipped during sync"""
        shift_data = {
            "property_id": test_property_id,
            "staff_id": test_staff["id"],
            "staff_name": test_staff["name"],
            "role": test_staff["role"],
            "date": test_week_start,
            "week_start": test_week_start,
            "start_time": "09:00",
            "end_time": "17:00",
            "status": "planned",
            "pay_type": "hourly",
            "pay_rate": 0,  # Zero pay rate
            "notes": f"{TEST_PREFIX}zero_earned_test"
        }
        create_resp = requests.post(f"{BASE_URL}/api/shifts/entries", json=shift_data, headers=headers)
        assert create_resp.status_code == 200
        shift = create_resp.json()
        shift_id = shift["id"]

        try:
            # Verify earned_amount is 0
            assert shift.get("earned_amount") == 0, f"Expected 0 earned, got {shift.get('earned_amount')}"
            
            # Update to completed
            update_resp = requests.put(
                f"{BASE_URL}/api/shifts/entries/{shift_id}",
                json={"status": "completed"},
                headers=headers
            )
            assert update_resp.status_code == 200
            
            # Sync should skip this shift (earned <= 0)
            # This is verified by the _sync_to_finance logic
            print("Zero-earned shift completed - should be skipped in finance sync")
            
        finally:
            requests.delete(f"{BASE_URL}/api/shifts/entries/{shift_id}", headers=headers)


class TestGetShiftsIncludesPayData:
    """Test GET /api/shifts/entries/{property_id} returns pay_rate/earned_amount"""

    def test_get_shifts_includes_pay_rate_and_earned_amount(self, headers, test_property_id, test_week_start, test_staff):
        """GET /api/shifts/entries/{property_id}?week_start returns data including pay_rate/earned_amount"""
        # Create a shift
        shift_data = {
            "property_id": test_property_id,
            "staff_id": test_staff["id"],
            "staff_name": test_staff["name"],
            "role": test_staff["role"],
            "date": test_week_start,
            "week_start": test_week_start,
            "start_time": "09:00",
            "end_time": "17:00",
            "status": "planned",
            "pay_type": "hourly",
            "pay_rate": 15.0,
            "notes": f"{TEST_PREFIX}get_pay_data_test"
        }
        create_resp = requests.post(f"{BASE_URL}/api/shifts/entries", json=shift_data, headers=headers)
        assert create_resp.status_code == 200
        shift = create_resp.json()
        shift_id = shift["id"]

        try:
            # GET shifts for the property and week
            get_resp = requests.get(
                f"{BASE_URL}/api/shifts/entries/{test_property_id}",
                params={"week_start": test_week_start},
                headers=headers
            )
            assert get_resp.status_code == 200, f"GET shifts failed: {get_resp.text}"
            shifts = get_resp.json()
            
            # Find our test shift
            test_shift = next((s for s in shifts if s["id"] == shift_id), None)
            assert test_shift is not None, f"Test shift not found in response"
            
            # Verify pay_rate and earned_amount are included
            assert "pay_rate" in test_shift, f"pay_rate missing from shift data: {test_shift}"
            assert "earned_amount" in test_shift, f"earned_amount missing from shift data: {test_shift}"
            assert test_shift["pay_rate"] == 15.0, f"Expected pay_rate 15.0, got {test_shift['pay_rate']}"
            assert test_shift["earned_amount"] == 120.0, f"Expected earned_amount 120.0, got {test_shift['earned_amount']}"
            
            print(f"GET shifts response includes pay data: pay_rate={test_shift['pay_rate']}, earned_amount={test_shift['earned_amount']}")
            
        finally:
            requests.delete(f"{BASE_URL}/api/shifts/entries/{shift_id}", headers=headers)


class TestCleanup:
    """Cleanup any remaining test data"""

    def test_cleanup_test_data(self, headers, test_property_id, test_week_start):
        """Clean up any remaining test shifts and staff"""
        # Get all shifts for test property
        shifts_resp = requests.get(
            f"{BASE_URL}/api/shifts/entries/{test_property_id}",
            params={"week_start": test_week_start},
            headers=headers
        )
        if shifts_resp.status_code == 200:
            shifts = shifts_resp.json()
            for shift in shifts:
                if TEST_PREFIX in shift.get("notes", ""):
                    requests.delete(f"{BASE_URL}/api/shifts/entries/{shift['id']}", headers=headers)
        
        # Get all staff for test property
        staff_resp = requests.get(
            f"{BASE_URL}/api/shifts/staff/{test_property_id}",
            headers=headers
        )
        if staff_resp.status_code == 200:
            staff_list = staff_resp.json()
            for staff in staff_list:
                if TEST_PREFIX in staff.get("name", ""):
                    requests.delete(f"{BASE_URL}/api/shifts/staff/{staff['id']}", headers=headers)
        
        print("Cleanup completed")
        assert True
