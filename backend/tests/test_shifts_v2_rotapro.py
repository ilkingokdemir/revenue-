"""
RotaPro v2 Shift Scheduler Tests
Tests for:
- Staff CRUD (create_shifts_router)
- Shift entries CRUD with auto hours_worked & earned_amount
- Bulk actions (copy-week, publish-all, clear-week)
- Payroll summary aggregation
- Conflict detection (long_shift, weekly_overtime, double_booking, consecutive_nights, leave_clash)
- Occupancy-based staffing needs
- AI auto-schedule (suggest + apply)
- Leave requests CRUD + leave balance (TR İş Kanunu)
- Clock-in/out events
- Open shifts + claim
- Sync to salaries
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test data storage
test_data = {
    "token": None,
    "staff_ids": [],
    "shift_ids": [],
    "leave_ids": [],
    "clock_event_ids": [],
    "open_shift_ids": [],
}


class TestAuth:
    """Authenticate first"""

    def test_login(self):
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"},
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data or "token" in data
        test_data["token"] = data.get("access_token") or data.get("token")
        print(f"✓ Login successful, token obtained")


class TestStaffCRUD:
    """Staff member CRUD operations"""

    def get_headers(self):
        return {"Authorization": f"Bearer {test_data['token']}"}

    def test_list_staff_initial(self):
        """GET /api/shifts/staff/{property_id} - smoke check"""
        response = requests.get(
            f"{BASE_URL}/api/shifts/staff/all", headers=self.get_headers()
        )
        assert response.status_code == 200, f"List staff failed: {response.text}"
        print(f"✓ List staff returned {len(response.json())} existing staff")

    def test_create_receptionist(self):
        """POST /api/shifts/staff - create receptionist with hourly pay"""
        response = requests.post(
            f"{BASE_URL}/api/shifts/staff",
            headers=self.get_headers(),
            json={
                "property_id": "default",
                "name": "TEST_Receptionist_Ali",
                "role": "receptionist",
                "pay_type": "hourly",
                "pay_rate": 25,
                "currency": "TRY",
                "email": "ali@test.hotel",
            },
        )
        assert response.status_code == 200, f"Create receptionist failed: {response.text}"
        data = response.json()
        assert data["name"] == "TEST_Receptionist_Ali"
        assert data["role"] == "receptionist"
        assert data["pay_type"] == "hourly"
        assert data["pay_rate"] == 25
        test_data["staff_ids"].append(data["id"])
        print(f"✓ Created receptionist: {data['id']}")

    def test_create_housekeeper(self):
        """POST /api/shifts/staff - create housekeeper with daily pay"""
        response = requests.post(
            f"{BASE_URL}/api/shifts/staff",
            headers=self.get_headers(),
            json={
                "property_id": "default",
                "name": "TEST_Housekeeper_Ayse",
                "role": "housekeeper",
                "pay_type": "daily",
                "pay_rate": 200,
                "currency": "TRY",
            },
        )
        assert response.status_code == 200, f"Create housekeeper failed: {response.text}"
        data = response.json()
        assert data["role"] == "housekeeper"
        assert data["pay_type"] == "daily"
        test_data["staff_ids"].append(data["id"])
        print(f"✓ Created housekeeper: {data['id']}")

    def test_create_maintenance(self):
        """POST /api/shifts/staff - create maintenance worker"""
        response = requests.post(
            f"{BASE_URL}/api/shifts/staff",
            headers=self.get_headers(),
            json={
                "property_id": "default",
                "name": "TEST_Maintenance_Mehmet",
                "role": "maintenance",
                "pay_type": "hourly",
                "pay_rate": 20,
                "currency": "TRY",
            },
        )
        assert response.status_code == 200, f"Create maintenance failed: {response.text}"
        data = response.json()
        test_data["staff_ids"].append(data["id"])
        print(f"✓ Created maintenance: {data['id']}")


class TestShiftEntriesCRUD:
    """Shift entries CRUD with auto calculations"""

    def get_headers(self):
        return {"Authorization": f"Bearer {test_data['token']}"}

    def get_week_start(self):
        """Get Monday of current week"""
        today = datetime.now()
        monday = today - timedelta(days=today.weekday())
        return monday.strftime("%Y-%m-%d")

    def test_create_shift_entry_auto_calc(self):
        """POST /api/shifts/entries - verify auto hours_worked & earned_amount"""
        week_start = self.get_week_start()
        shift_date = week_start  # Monday
        response = requests.post(
            f"{BASE_URL}/api/shifts/entries",
            headers=self.get_headers(),
            json={
                "property_id": "default",
                "staff_id": test_data["staff_ids"][0],  # receptionist
                "staff_name": "TEST_Receptionist_Ali",
                "role": "receptionist",
                "date": shift_date,
                "week_start": week_start,
                "start_time": "09:00",
                "end_time": "17:00",
                "pay_type": "hourly",
                "pay_rate": 25,
            },
        )
        assert response.status_code == 200, f"Create shift failed: {response.text}"
        data = response.json()
        # Verify auto-calculated fields
        assert data["hours_worked"] == 8.0, f"Expected 8h, got {data['hours_worked']}"
        assert data["earned_amount"] == 200.0, f"Expected 200 (8h*25), got {data['earned_amount']}"
        test_data["shift_ids"].append(data["id"])
        print(f"✓ Created shift with auto-calc: hours={data['hours_worked']}, earned={data['earned_amount']}")

    def test_list_shifts_by_week(self):
        """GET /api/shifts/entries/{property_id}?week_start=YYYY-MM-DD"""
        week_start = self.get_week_start()
        response = requests.get(
            f"{BASE_URL}/api/shifts/entries/default?week_start={week_start}",
            headers=self.get_headers(),
        )
        assert response.status_code == 200, f"List shifts failed: {response.text}"
        shifts = response.json()
        assert len(shifts) >= 1, "Should have at least 1 shift"
        print(f"✓ Listed {len(shifts)} shifts for week {week_start}")

    def test_update_shift_entry(self):
        """PUT /api/shifts/entries/{shift_id} - used by drag-drop"""
        if not test_data["shift_ids"]:
            pytest.skip("No shift to update")
        shift_id = test_data["shift_ids"][0]
        response = requests.put(
            f"{BASE_URL}/api/shifts/entries/{shift_id}",
            headers=self.get_headers(),
            json={"start_time": "10:00", "end_time": "18:00", "notes": "Updated via test"},
        )
        assert response.status_code == 200, f"Update shift failed: {response.text}"
        data = response.json()
        assert data["start_time"] == "10:00"
        assert data["end_time"] == "18:00"
        print(f"✓ Updated shift {shift_id}")


class TestBulkActions:
    """Bulk operations: copy-week, publish-all, clear-week"""

    def get_headers(self):
        return {"Authorization": f"Bearer {test_data['token']}"}

    def get_week_start(self):
        today = datetime.now()
        monday = today - timedelta(days=today.weekday())
        return monday.strftime("%Y-%m-%d")

    def test_publish_all(self):
        """POST /api/shifts/bulk/publish-all"""
        week_start = self.get_week_start()
        response = requests.post(
            f"{BASE_URL}/api/shifts/bulk/publish-all",
            headers=self.get_headers(),
            json={"week_start": week_start, "property_id": "default"},
        )
        assert response.status_code == 200, f"Publish all failed: {response.text}"
        data = response.json()
        assert "published" in data
        print(f"✓ Published {data['published']} shifts")

    def test_copy_week(self):
        """POST /api/shifts/bulk/copy-week"""
        week_start = self.get_week_start()
        source_week = week_start
        # Target = next week
        target_date = datetime.strptime(week_start, "%Y-%m-%d") + timedelta(days=7)
        target_week = target_date.strftime("%Y-%m-%d")
        response = requests.post(
            f"{BASE_URL}/api/shifts/bulk/copy-week",
            headers=self.get_headers(),
            json={
                "source_week": source_week,
                "target_week": target_week,
                "property_id": "default",
            },
        )
        assert response.status_code == 200, f"Copy week failed: {response.text}"
        data = response.json()
        assert "copied" in data
        print(f"✓ Copied {data['copied']} shifts from {source_week} to {target_week}")


class TestPayrollSummary:
    """Payroll aggregation"""

    def get_headers(self):
        return {"Authorization": f"Bearer {test_data['token']}"}

    def get_week_start(self):
        today = datetime.now()
        monday = today - timedelta(days=today.weekday())
        return monday.strftime("%Y-%m-%d")

    def test_payroll_summary(self):
        """GET /api/shifts/payroll/{property_id}?week_start"""
        week_start = self.get_week_start()
        response = requests.get(
            f"{BASE_URL}/api/shifts/payroll/default?week_start={week_start}",
            headers=self.get_headers(),
        )
        assert response.status_code == 200, f"Payroll summary failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        if data:
            assert "staff_id" in data[0]
            assert "total_hours" in data[0]
            assert "total_pay" in data[0]
            print(f"✓ Payroll summary: {len(data)} staff entries")
        else:
            print("✓ Payroll summary returned (empty - no shifts)")


class TestConflictDetection:
    """Conflict detection: long_shift, weekly_overtime, double_booking, consecutive_nights, leave_clash"""

    def get_headers(self):
        return {"Authorization": f"Bearer {test_data['token']}"}

    def get_week_start(self):
        today = datetime.now()
        monday = today - timedelta(days=today.weekday())
        return monday.strftime("%Y-%m-%d")

    def test_create_overtime_scenario(self):
        """Create 5 shifts of 10 hours each (50h > 45h TR limit) for overtime conflict"""
        week_start = self.get_week_start()
        staff_id = test_data["staff_ids"][1] if len(test_data["staff_ids"]) > 1 else test_data["staff_ids"][0]
        
        for i in range(5):
            shift_date = (datetime.strptime(week_start, "%Y-%m-%d") + timedelta(days=i)).strftime("%Y-%m-%d")
            response = requests.post(
                f"{BASE_URL}/api/shifts/entries",
                headers=self.get_headers(),
                json={
                    "property_id": "default",
                    "staff_id": staff_id,
                    "staff_name": "TEST_Housekeeper_Ayse",
                    "role": "housekeeper",
                    "date": shift_date,
                    "week_start": week_start,
                    "start_time": "07:00",
                    "end_time": "17:00",  # 10 hours
                    "pay_type": "daily",
                    "pay_rate": 200,
                },
            )
            assert response.status_code == 200
            test_data["shift_ids"].append(response.json()["id"])
        print(f"✓ Created 5 x 10h shifts for overtime test")

    def test_create_double_booking(self):
        """Create 2 shifts on same date for same staff"""
        week_start = self.get_week_start()
        staff_id = test_data["staff_ids"][0]
        shift_date = week_start  # Monday
        
        # Second shift on same day
        response = requests.post(
            f"{BASE_URL}/api/shifts/entries",
            headers=self.get_headers(),
            json={
                "property_id": "default",
                "staff_id": staff_id,
                "staff_name": "TEST_Receptionist_Ali",
                "role": "receptionist",
                "date": shift_date,
                "week_start": week_start,
                "start_time": "18:00",
                "end_time": "22:00",
                "pay_type": "hourly",
                "pay_rate": 25,
            },
        )
        assert response.status_code == 200
        test_data["shift_ids"].append(response.json()["id"])
        print(f"✓ Created double booking scenario")

    def test_detect_conflicts(self):
        """GET /api/shifts/conflicts/{property_id}?week_start - verify conflict types"""
        week_start = self.get_week_start()
        response = requests.get(
            f"{BASE_URL}/api/shifts/conflicts/default?week_start={week_start}",
            headers=self.get_headers(),
        )
        assert response.status_code == 200, f"Conflict detection failed: {response.text}"
        data = response.json()
        assert "conflicts" in data
        assert "count" in data
        
        # Check conflict structure
        conflict_types = set()
        for c in data["conflicts"]:
            assert "type" in c
            assert "severity" in c
            assert "staff_id" in c
            assert "message" in c
            conflict_types.add(c["type"])
        
        print(f"✓ Detected {data['count']} conflicts, types: {conflict_types}")
        
        # We should have at least weekly_overtime and double_booking
        if data["count"] > 0:
            assert "weekly_overtime" in conflict_types or "double_booking" in conflict_types, \
                f"Expected overtime or double_booking, got {conflict_types}"


class TestOccupancyNeeds:
    """Occupancy-based staffing recommendations"""

    def get_headers(self):
        return {"Authorization": f"Bearer {test_data['token']}"}

    def get_week_start(self):
        today = datetime.now()
        monday = today - timedelta(days=today.weekday())
        return monday.strftime("%Y-%m-%d")

    def test_occupancy_needs(self):
        """GET /api/shifts/occupancy-needs/{property_id}?week_start"""
        week_start = self.get_week_start()
        response = requests.get(
            f"{BASE_URL}/api/shifts/occupancy-needs/default?week_start={week_start}",
            headers=self.get_headers(),
        )
        assert response.status_code == 200, f"Occupancy needs failed: {response.text}"
        data = response.json()
        
        assert "week_start" in data
        assert "days" in data
        assert len(data["days"]) == 7, "Should return 7 days"
        
        # Check day structure
        day = data["days"][0]
        assert "date" in day
        assert "occupancy_pct" in day
        assert "needs" in day
        assert "housekeeper" in day["needs"]
        assert "receptionist" in day["needs"]
        assert "maintenance" in day["needs"]
        
        print(f"✓ Occupancy needs: 7 days returned with staffing recommendations")


class TestAISchedule:
    """AI auto-schedule: suggest + apply"""

    def get_headers(self):
        return {"Authorization": f"Bearer {test_data['token']}"}

    def get_week_start(self):
        today = datetime.now()
        monday = today - timedelta(days=today.weekday())
        return monday.strftime("%Y-%m-%d")

    def test_ai_suggest(self):
        """POST /api/shifts/ai-suggest/{property_id} - verify suggestions array"""
        week_start = self.get_week_start()
        response = requests.post(
            f"{BASE_URL}/api/shifts/ai-suggest/default",
            headers=self.get_headers(),
            json={"week_start": week_start},
            timeout=30,  # AI may take time
        )
        assert response.status_code == 200, f"AI suggest failed: {response.text}"
        data = response.json()
        
        assert "suggestions" in data
        assert "week_start" in data
        
        if data["suggestions"]:
            sg = data["suggestions"][0]
            assert "staff_id" in sg
            assert "date" in sg
            assert "start_time" in sg
            assert "end_time" in sg
            assert "role" in sg
            print(f"✓ AI suggest returned {len(data['suggestions'])} suggestions")
            test_data["ai_suggestions"] = data["suggestions"]
        else:
            print("✓ AI suggest returned (empty - may need more staff)")
            test_data["ai_suggestions"] = []

    def test_ai_apply(self):
        """POST /api/shifts/ai-apply/{property_id} - apply AI suggestions as draft shifts"""
        if not test_data.get("ai_suggestions"):
            pytest.skip("No AI suggestions to apply")
        
        week_start = self.get_week_start()
        response = requests.post(
            f"{BASE_URL}/api/shifts/ai-apply/default",
            headers=self.get_headers(),
            json={
                "week_start": week_start,
                "suggestions": test_data["ai_suggestions"][:3],  # Apply first 3
            },
        )
        assert response.status_code == 200, f"AI apply failed: {response.text}"
        data = response.json()
        assert "created" in data
        print(f"✓ AI apply created {data['created']} draft shifts")


class TestLeaveRequests:
    """Leave requests CRUD + balance (TR İş Kanunu)"""

    def get_headers(self):
        return {"Authorization": f"Bearer {test_data['token']}"}

    def test_create_leave_request(self):
        """POST /api/shifts/leaves - create leave with leave_type, start_date, end_date, days"""
        if not test_data["staff_ids"]:
            pytest.skip("No staff to create leave for")
        
        staff_id = test_data["staff_ids"][0]
        start_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        end_date = (datetime.now() + timedelta(days=34)).strftime("%Y-%m-%d")
        
        response = requests.post(
            f"{BASE_URL}/api/shifts/leaves",
            headers=self.get_headers(),
            json={
                "property_id": "default",
                "staff_id": staff_id,
                "staff_name": "TEST_Receptionist_Ali",
                "leave_type": "annual",
                "start_date": start_date,
                "end_date": end_date,
                "days": 5,
                "reason": "Test annual leave",
            },
        )
        assert response.status_code == 200, f"Create leave failed: {response.text}"
        data = response.json()
        assert data["leave_type"] == "annual"
        assert data["days"] == 5
        assert data["status"] == "pending"
        test_data["leave_ids"].append(data["id"])
        print(f"✓ Created leave request: {data['id']}")

    def test_list_leaves(self):
        """GET /api/shifts/leaves/{property_id}"""
        response = requests.get(
            f"{BASE_URL}/api/shifts/leaves/default",
            headers=self.get_headers(),
        )
        assert response.status_code == 200, f"List leaves failed: {response.text}"
        leaves = response.json()
        assert isinstance(leaves, list)
        print(f"✓ Listed {len(leaves)} leave requests")

    def test_update_leave_status(self):
        """PUT /api/shifts/leaves/{leave_id} - approve/reject"""
        if not test_data["leave_ids"]:
            pytest.skip("No leave to update")
        
        leave_id = test_data["leave_ids"][0]
        response = requests.put(
            f"{BASE_URL}/api/shifts/leaves/{leave_id}",
            headers=self.get_headers(),
            json={"status": "approved"},
        )
        assert response.status_code == 200, f"Update leave failed: {response.text}"
        data = response.json()
        assert data["status"] == "approved"
        print(f"✓ Approved leave {leave_id}")

    def test_leave_balance(self):
        """GET /api/shifts/leave-balance/{property_id} - TR İş Kanunu balance"""
        response = requests.get(
            f"{BASE_URL}/api/shifts/leave-balance/default",
            headers=self.get_headers(),
        )
        assert response.status_code == 200, f"Leave balance failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        
        if data:
            balance = data[0]
            assert "staff_id" in balance
            assert "entitled" in balance
            assert "used" in balance
            assert "remaining" in balance
            print(f"✓ Leave balance: {len(data)} staff, first has {balance['remaining']} days remaining")
        else:
            print("✓ Leave balance returned (empty - no staff)")


class TestClockInOut:
    """Clock-in/out events"""

    def get_headers(self):
        return {"Authorization": f"Bearer {test_data['token']}"}

    def test_clock_in(self):
        """POST /api/shifts/clock-in"""
        if not test_data["staff_ids"]:
            pytest.skip("No staff to clock in")
        
        staff_id = test_data["staff_ids"][0]
        response = requests.post(
            f"{BASE_URL}/api/shifts/clock-in",
            headers=self.get_headers(),
            json={
                "staff_id": staff_id,
                "staff_name": "TEST_Receptionist_Ali",
                "property_id": "default",
                "device": "web",
            },
        )
        assert response.status_code == 200, f"Clock in failed: {response.text}"
        data = response.json()
        assert "id" in data
        assert "clock_in" in data
        assert data["clock_out"] is None
        test_data["clock_event_ids"].append(data["id"])
        print(f"✓ Clocked in: {data['id']}")

    def test_clock_out(self):
        """POST /api/shifts/clock-out/{event_id} - compute actual_hours"""
        if not test_data["clock_event_ids"]:
            pytest.skip("No clock event to clock out")
        
        event_id = test_data["clock_event_ids"][0]
        response = requests.post(
            f"{BASE_URL}/api/shifts/clock-out/{event_id}",
            headers=self.get_headers(),
        )
        assert response.status_code == 200, f"Clock out failed: {response.text}"
        data = response.json()
        assert "clock_out" in data
        assert "actual_hours" in data
        print(f"✓ Clocked out: actual_hours={data['actual_hours']}")

    def test_list_clock_events(self):
        """GET /api/shifts/clock-events/{property_id}?days=7"""
        response = requests.get(
            f"{BASE_URL}/api/shifts/clock-events/default?days=7",
            headers=self.get_headers(),
        )
        assert response.status_code == 200, f"List clock events failed: {response.text}"
        events = response.json()
        assert isinstance(events, list)
        print(f"✓ Listed {len(events)} clock events")


class TestOpenShifts:
    """Open shifts + claim"""

    def get_headers(self):
        return {"Authorization": f"Bearer {test_data['token']}"}

    def test_create_open_shift(self):
        """POST /api/shifts/open - create open shift"""
        shift_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        response = requests.post(
            f"{BASE_URL}/api/shifts/open",
            headers=self.get_headers(),
            json={
                "property_id": "default",
                "date": shift_date,
                "start_time": "14:00",
                "end_time": "22:00",
                "role": "receptionist",
                "notes": "Evening shift available",
            },
        )
        assert response.status_code == 200, f"Create open shift failed: {response.text}"
        data = response.json()
        assert data["status"] == "open"
        assert data["claimed_by"] is None
        test_data["open_shift_ids"].append(data["id"])
        print(f"✓ Created open shift: {data['id']}")

    def test_list_open_shifts(self):
        """GET /api/shifts/open/{property_id}"""
        response = requests.get(
            f"{BASE_URL}/api/shifts/open/default",
            headers=self.get_headers(),
        )
        assert response.status_code == 200, f"List open shifts failed: {response.text}"
        shifts = response.json()
        assert isinstance(shifts, list)
        print(f"✓ Listed {len(shifts)} open shifts")

    def test_claim_open_shift(self):
        """POST /api/shifts/open/{open_id}/claim - status -> claimed"""
        if not test_data["open_shift_ids"]:
            pytest.skip("No open shift to claim")
        
        open_id = test_data["open_shift_ids"][0]
        staff_id = test_data["staff_ids"][0] if test_data["staff_ids"] else "test-staff"
        
        response = requests.post(
            f"{BASE_URL}/api/shifts/open/{open_id}/claim",
            headers=self.get_headers(),
            json={
                "staff_id": staff_id,
                "staff_name": "TEST_Receptionist_Ali",
            },
        )
        assert response.status_code == 200, f"Claim open shift failed: {response.text}"
        data = response.json()
        assert data["status"] == "claimed"
        assert data["claimed_by"] == staff_id
        print(f"✓ Claimed open shift: {open_id}")


class TestSyncToSalaries:
    """Sync completed shifts to finance_earned_salaries"""

    def get_headers(self):
        return {"Authorization": f"Bearer {test_data['token']}"}

    def get_week_start(self):
        today = datetime.now()
        monday = today - timedelta(days=today.weekday())
        return monday.strftime("%Y-%m-%d")

    def test_mark_shifts_completed(self):
        """First mark shifts as completed"""
        week_start = self.get_week_start()
        response = requests.post(
            f"{BASE_URL}/api/shifts/bulk/mark-completed",
            headers=self.get_headers(),
            json={"week_start": week_start, "property_id": "default"},
        )
        assert response.status_code == 200, f"Mark completed failed: {response.text}"
        data = response.json()
        print(f"✓ Marked {data.get('completed', 0)} shifts as completed")

    def test_sync_to_salaries(self):
        """POST /api/shifts/sync-to-salaries"""
        week_start = self.get_week_start()
        response = requests.post(
            f"{BASE_URL}/api/shifts/sync-to-salaries",
            headers=self.get_headers(),
            json={"week_start": week_start, "property_id": "default"},
        )
        assert response.status_code == 200, f"Sync to salaries failed: {response.text}"
        data = response.json()
        assert "synced" in data
        assert "total_shifts_processed" in data
        print(f"✓ Synced {data['synced']} shifts to salaries (processed {data['total_shifts_processed']})")


class TestCleanup:
    """Cleanup test data"""

    def get_headers(self):
        return {"Authorization": f"Bearer {test_data['token']}"}

    def get_week_start(self):
        today = datetime.now()
        monday = today - timedelta(days=today.weekday())
        return monday.strftime("%Y-%m-%d")

    def test_delete_shift_entries(self):
        """DELETE /api/shifts/entries/{shift_id}"""
        deleted = 0
        for shift_id in test_data["shift_ids"]:
            response = requests.delete(
                f"{BASE_URL}/api/shifts/entries/{shift_id}",
                headers=self.get_headers(),
            )
            if response.status_code == 200:
                deleted += 1
        print(f"✓ Deleted {deleted} test shift entries")

    def test_clear_week(self):
        """POST /api/shifts/bulk/clear-week - cleanup"""
        week_start = self.get_week_start()
        # Clear next week (where we copied)
        next_week = (datetime.strptime(week_start, "%Y-%m-%d") + timedelta(days=7)).strftime("%Y-%m-%d")
        response = requests.post(
            f"{BASE_URL}/api/shifts/bulk/clear-week",
            headers=self.get_headers(),
            json={"week_start": next_week, "property_id": "default"},
        )
        assert response.status_code == 200
        print(f"✓ Cleared next week shifts")

    def test_delete_staff(self):
        """DELETE /api/shifts/staff/{staff_id}"""
        deleted = 0
        for staff_id in test_data["staff_ids"]:
            response = requests.delete(
                f"{BASE_URL}/api/shifts/staff/{staff_id}",
                headers=self.get_headers(),
            )
            if response.status_code == 200:
                deleted += 1
        print(f"✓ Deleted {deleted} test staff members")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
