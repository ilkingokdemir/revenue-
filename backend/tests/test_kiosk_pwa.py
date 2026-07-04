"""
Kiosk PWA Backend Tests — Self-Service Check-In (Iter 359)
Tests for public kiosk endpoints (no auth required):
- GET /api/kiosk/{property_id}/config
- POST /api/kiosk/{property_id}/lookup
- POST /api/kiosk/{property_id}/checkin/{booking_id}
- GET /api/kiosk/{property_id}/stats
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
PROPERTY_ID = "camden-suites"
TEST_BOOKING_REF = "MHB-K13F3"
TEST_BOOKING_ID = "5197869f-d887-4f76-b3d9-66444715ca25"


class TestKioskConfig:
    """Test GET /api/kiosk/{property_id}/config - public endpoint"""
    
    def test_config_returns_property_branding(self):
        """Backend #1: GET /api/kiosk/camden-suites/config returns property branding"""
        response = requests.get(f"{BASE_URL}/api/kiosk/{PROPERTY_ID}/config")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Verify required fields
        assert data.get("name") == "Camden Apartments", f"Expected 'Camden Apartments', got {data.get('name')}"
        assert "brand_color" in data, "Missing brand_color"
        assert "checkin_time" in data, "Missing checkin_time"
        assert data.get("checkin_time") == "15:00", f"Expected '15:00', got {data.get('checkin_time')}"
        assert data.get("currency") == "GBP", f"Expected 'GBP', got {data.get('currency')}"
        print(f"✓ Config returned: name={data['name']}, currency={data['currency']}, checkin_time={data['checkin_time']}")
    
    def test_config_invalid_property_returns_404(self):
        """Config for non-existent property returns 404"""
        response = requests.get(f"{BASE_URL}/api/kiosk/invalid-property-xyz/config")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Invalid property returns 404")


class TestKioskLookup:
    """Test POST /api/kiosk/{property_id}/lookup - public endpoint"""
    
    def test_lookup_empty_body_returns_400(self):
        """Backend #2a: POST /api/kiosk/camden-suites/lookup with {} returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/kiosk/{PROPERTY_ID}/lookup",
            json={},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        
        data = response.json()
        assert "kimlik bilgisi" in data.get("detail", "").lower() or "en az bir" in data.get("detail", "").lower(), \
            f"Expected Turkish error message about credentials, got: {data.get('detail')}"
        print(f"✓ Empty body returns 400 with message: {data.get('detail')}")
    
    def test_lookup_valid_booking_ref_returns_booking(self):
        """Backend #2b: POST /api/kiosk/camden-suites/lookup with {booking_ref:'MHB-K13F3'} returns booking"""
        response = requests.post(
            f"{BASE_URL}/api/kiosk/{PROPERTY_ID}/lookup",
            json={"booking_ref": TEST_BOOKING_REF},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("count") == 1, f"Expected count=1, got {data.get('count')}"
        assert "bookings" in data, "Missing bookings array"
        assert len(data["bookings"]) == 1, f"Expected 1 booking, got {len(data['bookings'])}"
        
        booking = data["bookings"][0]
        assert booking.get("guest_name") == "Kiosk Test User", f"Expected 'Kiosk Test User', got {booking.get('guest_name')}"
        assert booking.get("room_number") == "204", f"Expected room '204', got {booking.get('room_number')}"
        # Note: ready_for_checkin may be false if already checked in
        print(f"✓ Lookup returned booking: guest={booking['guest_name']}, room={booking['room_number']}, status={booking.get('status')}")
    
    def test_lookup_invalid_booking_ref_returns_404(self):
        """Backend #2c: POST /api/kiosk/camden-suites/lookup with {booking_ref:'ZZZ-FAKE'} returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/kiosk/{PROPERTY_ID}/lookup",
            json={"booking_ref": "ZZZ-FAKE"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        
        data = response.json()
        assert "bulunamadı" in data.get("detail", "").lower(), \
            f"Expected Turkish 'not found' message, got: {data.get('detail')}"
        print(f"✓ Invalid booking ref returns 404 with message: {data.get('detail')}")


class TestKioskCheckin:
    """Test POST /api/kiosk/{property_id}/checkin/{booking_id} - public endpoint"""
    
    def test_checkin_idempotent_returns_room_and_code(self):
        """Backend #3: POST /api/kiosk/camden-suites/checkin/{booking_id} returns room + door code (idempotent)"""
        response = requests.post(
            f"{BASE_URL}/api/kiosk/{PROPERTY_ID}/checkin/{TEST_BOOKING_ID}",
            json={"signature": "John", "id_scan_ref": ""},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, f"Expected ok=true, got {data.get('ok')}"
        # Since booking is already checked in, already should be true
        assert data.get("already") is True, f"Expected already=true (idempotent), got {data.get('already')}"
        assert data.get("room_number") == "204", f"Expected room '204', got {data.get('room_number')}"
        
        # Door code should be 4 digits
        door_code = data.get("door_code", "")
        assert len(door_code) == 4 and door_code.isdigit(), f"Expected 4-digit door code, got: {door_code}"
        assert "checkin_time" in data, "Missing checkin_time"
        print(f"✓ Checkin returned: room={data['room_number']}, door_code={data['door_code']}, already={data['already']}")
    
    def test_checkin_invalid_booking_returns_404(self):
        """Checkin for non-existent booking returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/kiosk/{PROPERTY_ID}/checkin/invalid-booking-id-xyz",
            json={"signature": "Test", "id_scan_ref": ""},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Invalid booking ID returns 404")


class TestKioskStats:
    """Test GET /api/kiosk/{property_id}/stats - public endpoint"""
    
    def test_stats_returns_kpi_data(self):
        """Backend #4: GET /api/kiosk/camden-suites/stats returns KPI data"""
        response = requests.get(f"{BASE_URL}/api/kiosk/{PROPERTY_ID}/stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "total_kiosk_checkins" in data, "Missing total_kiosk_checkins"
        assert "today" in data, "Missing today count"
        assert "lookup_misses" in data, "Missing lookup_misses"
        
        # Values should be non-negative integers
        assert isinstance(data["total_kiosk_checkins"], int) and data["total_kiosk_checkins"] >= 0
        assert isinstance(data["today"], int) and data["today"] >= 0
        assert isinstance(data["lookup_misses"], int) and data["lookup_misses"] >= 0
        print(f"✓ Stats returned: total={data['total_kiosk_checkins']}, today={data['today']}, misses={data['lookup_misses']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
