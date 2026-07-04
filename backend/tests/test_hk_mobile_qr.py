"""
Housekeeping Mobile PWA + Kiosk QR Token Tests — Batch 3 F3 (Iter 360)
Tests for:
- QR token generation: GET /api/kiosk/{property_id}/qr-token/{booking_id} (admin auth)
- QR token redeem: POST /api/kiosk/{property_id}/qr-redeem (public)
- HK stats: GET /api/housekeeping/rooms/{property_id}/stats (admin auth)
- HK transition: PUT /api/housekeeping/rooms/{room_id}/status (admin auth)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
PROPERTY_ID = "camden-suites"
TEST_BOOKING_ID = "5197869f-d887-4f76-b3d9-66444715ca25"


@pytest.fixture(scope="module")
def auth_token():
    """Get admin auth token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"}
    )
    if response.status_code != 200:
        pytest.skip("Auth failed - skipping authenticated tests")
    return response.json().get("token")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Auth headers for admin requests"""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestQRToken:
    """Test QR token generation and redemption"""
    
    def test_qr_token_generation(self, auth_headers):
        """Backend #1: GET /api/kiosk/camden-suites/qr-token/{booking_id} returns token, kiosk_url, expires_at"""
        response = requests.get(
            f"{BASE_URL}/api/kiosk/{PROPERTY_ID}/qr-token/{TEST_BOOKING_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "token" in data, "Missing token field"
        assert "kiosk_url" in data, "Missing kiosk_url field"
        assert "expires_at" in data, "Missing expires_at field"
        
        # Token should be a non-empty string
        assert isinstance(data["token"], str) and len(data["token"]) > 10, f"Invalid token: {data['token']}"
        # kiosk_url should contain the token
        assert data["token"] in data["kiosk_url"], "kiosk_url should contain the token"
        assert f"/kiosk/{PROPERTY_ID}" in data["kiosk_url"], "kiosk_url should contain property path"
        print(f"✓ QR token generated: {data['token'][:20]}..., expires: {data['expires_at']}")
    
    def test_qr_redeem_valid_token(self, auth_headers):
        """Backend #2a: POST /api/kiosk/camden-suites/qr-redeem with valid token returns booking"""
        # First generate a token
        gen_response = requests.get(
            f"{BASE_URL}/api/kiosk/{PROPERTY_ID}/qr-token/{TEST_BOOKING_ID}",
            headers=auth_headers
        )
        assert gen_response.status_code == 200
        token = gen_response.json()["token"]
        
        # Now redeem it (public endpoint, no auth needed)
        response = requests.post(
            f"{BASE_URL}/api/kiosk/{PROPERTY_ID}/qr-redeem",
            json={"token": token},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "booking" in data, "Missing booking field"
        booking = data["booking"]
        assert booking.get("guest_name") == "Kiosk Test User", f"Expected 'Kiosk Test User', got {booking.get('guest_name')}"
        assert booking.get("room_number") == "204", f"Expected room '204', got {booking.get('room_number')}"
        print(f"✓ QR redeem returned booking: guest={booking['guest_name']}, room={booking['room_number']}")
    
    def test_qr_redeem_invalid_token(self):
        """Backend #2b: POST /api/kiosk/camden-suites/qr-redeem with invalid token returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/kiosk/{PROPERTY_ID}/qr-redeem",
            json={"token": "invalid-token-xyz"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        
        data = response.json()
        # Turkish error message: "Token geçersiz veya süresi dolmuş"
        assert "geçersiz" in data.get("detail", "").lower() or "token" in data.get("detail", "").lower(), \
            f"Expected Turkish error about invalid token, got: {data.get('detail')}"
        print(f"✓ Invalid token returns 404 with message: {data.get('detail')}")


class TestHousekeepingStats:
    """Test housekeeping stats endpoint"""
    
    def test_hk_stats_returns_counts(self, auth_headers):
        """Backend #3: GET /api/housekeeping/rooms/camden-suites/stats returns all status counts"""
        response = requests.get(
            f"{BASE_URL}/api/housekeeping/rooms/{PROPERTY_ID}/stats",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify all required fields
        required_fields = ["total", "clean", "dirty", "inspected", "in_progress", "out_of_order"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
            assert isinstance(data[field], int), f"{field} should be int, got {type(data[field])}"
            assert data[field] >= 0, f"{field} should be non-negative"
        
        # Camden has 15 rooms seeded
        assert data["total"] == 15, f"Expected total=15, got {data['total']}"
        print(f"✓ HK stats: total={data['total']}, clean={data['clean']}, dirty={data['dirty']}, inspected={data['inspected']}, in_progress={data['in_progress']}")


class TestHousekeepingTransition:
    """Test room status transitions"""
    
    def test_transition_dirty_to_in_progress(self, auth_headers):
        """Backend #4a: PUT /api/housekeeping/rooms/{room_id}/status dirty→in_progress"""
        # Get a dirty room
        rooms_response = requests.get(
            f"{BASE_URL}/api/housekeeping/rooms/{PROPERTY_ID}?status=dirty",
            headers=auth_headers
        )
        assert rooms_response.status_code == 200
        dirty_rooms = rooms_response.json()
        if not dirty_rooms:
            pytest.skip("No dirty rooms available for testing")
        
        room = dirty_rooms[0]
        room_id = room["id"]
        
        # Transition to in_progress
        response = requests.put(
            f"{BASE_URL}/api/housekeeping/rooms/{room_id}/status",
            json={"status": "in_progress"},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("status") == "in_progress", f"Expected status='in_progress', got {data.get('status')}"
        assert "updated_at" in data, "Missing updated_at"
        print(f"✓ Room {data['room_number']} transitioned to in_progress")
        
        # Cleanup: transition back to dirty
        requests.put(
            f"{BASE_URL}/api/housekeeping/rooms/{room_id}/status",
            json={"status": "dirty"},
            headers=auth_headers
        )
    
    def test_full_transition_cycle(self, auth_headers):
        """Backend #4b: Full cycle dirty→in_progress→clean→inspected"""
        # Get a dirty room
        rooms_response = requests.get(
            f"{BASE_URL}/api/housekeeping/rooms/{PROPERTY_ID}?status=dirty",
            headers=auth_headers
        )
        assert rooms_response.status_code == 200
        dirty_rooms = rooms_response.json()
        if not dirty_rooms:
            pytest.skip("No dirty rooms available for testing")
        
        room = dirty_rooms[0]
        room_id = room["id"]
        room_number = room["room_number"]
        
        # dirty → in_progress
        r1 = requests.put(
            f"{BASE_URL}/api/housekeeping/rooms/{room_id}/status",
            json={"status": "in_progress"},
            headers=auth_headers
        )
        assert r1.status_code == 200 and r1.json().get("status") == "in_progress"
        
        # in_progress → clean
        r2 = requests.put(
            f"{BASE_URL}/api/housekeeping/rooms/{room_id}/status",
            json={"status": "clean"},
            headers=auth_headers
        )
        assert r2.status_code == 200 and r2.json().get("status") == "clean"
        # Should have last_cleaned_at and last_cleaned_by set
        assert r2.json().get("last_cleaned_at"), "Missing last_cleaned_at after clean transition"
        assert r2.json().get("last_cleaned_by"), "Missing last_cleaned_by after clean transition"
        
        # clean → inspected
        r3 = requests.put(
            f"{BASE_URL}/api/housekeeping/rooms/{room_id}/status",
            json={"status": "inspected"},
            headers=auth_headers
        )
        assert r3.status_code == 200 and r3.json().get("status") == "inspected"
        
        print(f"✓ Room {room_number} full cycle: dirty→in_progress→clean→inspected")
        
        # Cleanup: reset to dirty
        requests.put(
            f"{BASE_URL}/api/housekeeping/rooms/{room_id}/status",
            json={"status": "dirty"},
            headers=auth_headers
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
