"""
Spaces Monetization (Mews-parity Batch 2) Backend Tests
--------------------------------------------------------
Tests for hourly booking engine: parking, meeting rooms, EV chargers, coworking desks, lockers.
Endpoints tested:
  - POST /api/spaces/{pid}/seed (quick-start seed)
  - GET /api/spaces/{pid} (list spaces)
  - POST /api/space-bookings (create booking)
  - GET /api/spaces/{pid}/revenue (revenue KPIs)
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
PROPERTY_ID = "camden-suites"

class TestSpacesMonetization:
    """Test suite for Spaces Monetization feature"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: login as admin and get auth cookie"""
        self.session = requests.Session()
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        self.user = login_resp.json()
        yield
        # Cleanup: delete seeded spaces after tests
        # Note: We don't cleanup to allow frontend testing
    
    def test_01_seed_spaces_success(self):
        """Backend #1: POST /api/spaces/camden-suites/seed as admin → returns {ok:true, seeded:6, spaces:[...]}"""
        # First, clear any existing spaces for clean test
        existing = self.session.get(f"{BASE_URL}/api/spaces/{PROPERTY_ID}")
        if existing.status_code == 200 and len(existing.json()) > 0:
            # Delete existing spaces
            for space in existing.json():
                self.session.delete(f"{BASE_URL}/api/spaces/{PROPERTY_ID}/{space['id']}")
        
        # Now seed
        resp = self.session.post(f"{BASE_URL}/api/spaces/{PROPERTY_ID}/seed")
        assert resp.status_code == 200, f"Seed failed: {resp.status_code} - {resp.text}"
        
        data = resp.json()
        assert data.get("ok") == True, f"Expected ok:true, got {data}"
        assert data.get("seeded") == 6, f"Expected seeded:6, got {data.get('seeded')}"
        assert "spaces" in data, "Missing 'spaces' in response"
        assert len(data["spaces"]) == 6, f"Expected 6 spaces, got {len(data['spaces'])}"
        
        # Verify space names and rates
        space_names = {s["name"] for s in data["spaces"]}
        expected_names = {
            "Otopark Yeri #1",
            "Elektrikli Şarj İstasyonu",
            "Executive Toplantı Odası",
            "Board Room",
            "Co-working Desk",
            "Bagaj Dolabı"
        }
        assert space_names == expected_names, f"Space names mismatch. Got: {space_names}"
        print(f"✅ Seed successful: {data['seeded']} spaces created")
    
    def test_02_list_spaces_verify_details(self):
        """Backend #2: GET /api/spaces/camden-suites → returns 6 spaces with correct details"""
        resp = self.session.get(f"{BASE_URL}/api/spaces/{PROPERTY_ID}")
        assert resp.status_code == 200, f"List failed: {resp.status_code} - {resp.text}"
        
        spaces = resp.json()
        assert len(spaces) >= 6, f"Expected at least 6 spaces, got {len(spaces)}"
        
        # Create lookup by name
        by_name = {s["name"]: s for s in spaces}
        
        # Verify Otopark Yeri #1 (parking £3/h)
        parking = by_name.get("Otopark Yeri #1")
        assert parking is not None, "Missing 'Otopark Yeri #1'"
        assert parking["kind"] == "parking", f"Expected kind=parking, got {parking['kind']}"
        assert parking["rate_per_unit"] == 3.0 or parking.get("hourly_rate") == 3.0, f"Expected rate=3, got {parking}"
        
        # Verify Elektrikli Şarj İstasyonu (ev_charger £5/h)
        ev = by_name.get("Elektrikli Şarj İstasyonu")
        assert ev is not None, "Missing 'Elektrikli Şarj İstasyonu'"
        assert ev["kind"] == "ev_charger", f"Expected kind=ev_charger, got {ev['kind']}"
        assert ev["rate_per_unit"] == 5.0 or ev.get("hourly_rate") == 5.0, f"Expected rate=5, got {ev}"
        
        # Verify Executive Toplantı Odası (meeting_room £50/h)
        meeting = by_name.get("Executive Toplantı Odası")
        assert meeting is not None, "Missing 'Executive Toplantı Odası'"
        assert meeting["kind"] == "meeting_room", f"Expected kind=meeting_room, got {meeting['kind']}"
        assert meeting["rate_per_unit"] == 50.0 or meeting.get("hourly_rate") == 50.0, f"Expected rate=50, got {meeting}"
        
        # Verify Board Room (meeting_room £90/h)
        board = by_name.get("Board Room")
        assert board is not None, "Missing 'Board Room'"
        assert board["kind"] == "meeting_room", f"Expected kind=meeting_room, got {board['kind']}"
        assert board["rate_per_unit"] == 90.0 or board.get("hourly_rate") == 90.0, f"Expected rate=90, got {board}"
        
        # Verify Co-working Desk (cabana £8/h)
        cowork = by_name.get("Co-working Desk")
        assert cowork is not None, "Missing 'Co-working Desk'"
        assert cowork["kind"] == "cabana", f"Expected kind=cabana, got {cowork['kind']}"
        assert cowork["rate_per_unit"] == 8.0 or cowork.get("hourly_rate") == 8.0, f"Expected rate=8, got {cowork}"
        
        # Verify Bagaj Dolabı (locker £5/day)
        locker = by_name.get("Bagaj Dolabı")
        assert locker is not None, "Missing 'Bagaj Dolabı'"
        assert locker["kind"] == "locker", f"Expected kind=locker, got {locker['kind']}"
        assert locker["rate_per_unit"] == 5.0 or locker.get("hourly_rate") == 5.0, f"Expected rate=5, got {locker}"
        
        print(f"✅ All 6 spaces verified with correct names, kinds, and rates")
        return by_name
    
    def test_03_create_booking_verify_pricing(self):
        """Backend #3: POST /api/space-bookings with 2-hour meeting room → verify units=2, price=100"""
        # First get the Executive Toplantı Odası space_id
        spaces_resp = self.session.get(f"{BASE_URL}/api/spaces/{PROPERTY_ID}")
        spaces = spaces_resp.json()
        meeting_room = next((s for s in spaces if s["name"] == "Executive Toplantı Odası"), None)
        assert meeting_room is not None, "Executive Toplantı Odası not found"
        
        # Create booking for 2 hours
        booking_data = {
            "space_id": meeting_room["id"],
            "start": "2026-07-01T14:00:00",
            "end": "2026-07-01T16:00:00",
            "guest_name": "Test Guest",
            "guest_email": "t@t.co"
        }
        
        resp = self.session.post(f"{BASE_URL}/api/space-bookings", json=booking_data)
        assert resp.status_code == 200, f"Booking failed: {resp.status_code} - {resp.text}"
        
        data = resp.json()
        assert data.get("ok") == True, f"Expected ok:true, got {data}"
        
        booking = data.get("booking", {})
        assert booking.get("units") == 2, f"Expected units=2, got {booking.get('units')}"
        assert booking.get("price") == 100.0, f"Expected price=100, got {booking.get('price')}"
        assert booking.get("space_name") == "Executive Toplantı Odası", f"Wrong space name: {booking.get('space_name')}"
        assert booking.get("guest_name") == "Test Guest", f"Wrong guest name: {booking.get('guest_name')}"
        
        print(f"✅ Booking created: {booking['units']} units × £50/h = £{booking['price']}")
        return booking
    
    def test_04_revenue_kpis(self):
        """Backend #4: GET /api/spaces/camden-suites/revenue?days=30 → verify revenue KPIs"""
        resp = self.session.get(f"{BASE_URL}/api/spaces/{PROPERTY_ID}/revenue?days=30")
        assert resp.status_code == 200, f"Revenue failed: {resp.status_code} - {resp.text}"
        
        data = resp.json()
        
        # Verify structure
        assert "total_revenue" in data, "Missing total_revenue"
        assert "total_bookings" in data, "Missing total_bookings"
        assert "top_space" in data, "Missing top_space"
        
        # After test_03, we should have at least 1 booking with £100 revenue
        assert data["total_revenue"] >= 100, f"Expected total_revenue >= 100, got {data['total_revenue']}"
        assert data["total_bookings"] >= 1, f"Expected total_bookings >= 1, got {data['total_bookings']}"
        
        # Top space should be Executive Toplantı Odası with £100
        if data["top_space"]:
            assert data["top_space"]["name"] == "Executive Toplantı Odası", f"Expected top_space=Executive Toplantı Odası, got {data['top_space']['name']}"
            assert data["top_space"]["revenue"] >= 100, f"Expected top_space revenue >= 100, got {data['top_space']['revenue']}"
        
        print(f"✅ Revenue KPIs: total_revenue=£{data['total_revenue']}, total_bookings={data['total_bookings']}, top_space={data.get('top_space', {}).get('name')}")
    
    def test_05_seed_idempotent_guard(self):
        """Backend #5: Repeat POST /api/spaces/camden-suites/seed → should return 400 with 'Zaten X space var'"""
        resp = self.session.post(f"{BASE_URL}/api/spaces/{PROPERTY_ID}/seed")
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        
        # Check error message contains Turkish "Zaten" (already)
        error_detail = resp.json().get("detail", "")
        assert "Zaten" in error_detail, f"Expected 'Zaten X space var' message, got: {error_detail}"
        
        print(f"✅ Idempotent guard working: {error_detail}")
    
    def test_06_unauthorized_access(self):
        """Test that unauthenticated requests are rejected"""
        # Create new session without auth
        unauth_session = requests.Session()
        
        resp = unauth_session.get(f"{BASE_URL}/api/spaces/{PROPERTY_ID}")
        assert resp.status_code == 401, f"Expected 401 for unauthenticated request, got {resp.status_code}"
        
        resp = unauth_session.post(f"{BASE_URL}/api/spaces/{PROPERTY_ID}/seed")
        assert resp.status_code == 401, f"Expected 401 for unauthenticated seed, got {resp.status_code}"
        
        print("✅ Unauthorized access properly rejected")
    
    def test_07_booking_validation(self):
        """Test booking validation - missing required fields"""
        # Missing guest_name
        resp = self.session.post(f"{BASE_URL}/api/space-bookings", json={
            "space_id": "some-id",
            "start": "2026-07-01T14:00:00",
            "end": "2026-07-01T16:00:00"
        })
        assert resp.status_code == 400, f"Expected 400 for missing guest_name, got {resp.status_code}"
        
        # Missing space_id
        resp = self.session.post(f"{BASE_URL}/api/space-bookings", json={
            "start": "2026-07-01T14:00:00",
            "end": "2026-07-01T16:00:00",
            "guest_name": "Test"
        })
        assert resp.status_code == 400, f"Expected 400 for missing space_id, got {resp.status_code}"
        
        print("✅ Booking validation working correctly")
    
    def test_08_nonexistent_space_booking(self):
        """Test booking with nonexistent space_id returns 404"""
        resp = self.session.post(f"{BASE_URL}/api/space-bookings", json={
            "space_id": "nonexistent-space-id",
            "start": "2026-07-01T14:00:00",
            "end": "2026-07-01T16:00:00",
            "guest_name": "Test",
            "guest_email": "t@t.co"
        })
        assert resp.status_code == 404, f"Expected 404 for nonexistent space, got {resp.status_code}"
        
        print("✅ Nonexistent space properly returns 404")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
