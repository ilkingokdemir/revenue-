"""
Booking Engine API Tests - Iteration 23
Tests for the new Booking Engine module including:
- Public booking engine endpoints (property info, rooms, reserve, reservation lookup)
- Admin room types CRUD
- Admin bookings management
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"

# Test data
TEST_PROPERTY_ID = "aldgate-flats"
TEST_GUEST_NAME = "TEST_BookingEngine_Guest"
TEST_GUEST_EMAIL = "test_booking@example.com"


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def auth_token(api_client):
    """Get authentication token"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Authentication failed - skipping authenticated tests")


@pytest.fixture(scope="module")
def authenticated_client(api_client, auth_token):
    """Session with auth header"""
    api_client.headers.update({"Authorization": f"Bearer {auth_token}"})
    return api_client


class TestPublicBookingEngineEndpoints:
    """Test public booking engine endpoints (no auth required)"""
    
    def test_get_property_info(self, api_client):
        """GET /api/booking/property/{property_id} returns property with room types"""
        response = api_client.get(f"{BASE_URL}/api/booking/property/{TEST_PROPERTY_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "id" in data or "name" in data, "Property should have id or name"
        assert "room_types" in data, "Property should include room_types"
        assert isinstance(data["room_types"], list), "room_types should be a list"
        print(f"Property info: {data.get('name')}, {len(data.get('room_types', []))} room types")
    
    def test_get_property_info_not_found(self, api_client):
        """GET /api/booking/property/{invalid_id} returns 404"""
        response = api_client.get(f"{BASE_URL}/api/booking/property/nonexistent-property-xyz")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
    
    def test_get_booking_rooms(self, api_client):
        """GET /api/booking/rooms/{property_id} returns available room types"""
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        day_after = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
        
        response = api_client.get(
            f"{BASE_URL}/api/booking/rooms/{TEST_PROPERTY_ID}",
            params={"check_in": tomorrow, "check_out": day_after, "adults": 2, "children": 0}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Should return a list of rooms"
        assert len(data) >= 1, "Should have at least 1 room type"
        
        # Verify room structure
        room = data[0]
        assert "id" in room, "Room should have id"
        assert "name" in room, "Room should have name"
        assert "base_price" in room, "Room should have base_price"
        assert "available_rooms" in room, "Room should have available_rooms"
        assert "is_available" in room, "Room should have is_available"
        print(f"Found {len(data)} room types for {TEST_PROPERTY_ID}")
    
    def test_get_booking_rooms_without_dates(self, api_client):
        """GET /api/booking/rooms/{property_id} without dates returns all rooms as available"""
        response = api_client.get(f"{BASE_URL}/api/booking/rooms/{TEST_PROPERTY_ID}")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        for room in data:
            assert room.get("is_available") == True, "All rooms should be available without date filter"
    
    def test_check_availability(self, api_client):
        """GET /api/booking/availability/{property_id} returns availability summary"""
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        day_after = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
        
        response = api_client.get(
            f"{BASE_URL}/api/booking/availability/{TEST_PROPERTY_ID}",
            params={"check_in": tomorrow, "check_out": day_after}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "property_id" in data
        assert "rooms" in data
        assert isinstance(data["rooms"], list)
        print(f"Availability check: {len(data['rooms'])} room types")
    
    def test_get_booking_reviews(self, api_client):
        """GET /api/booking/reviews/{property_id} returns positive reviews"""
        response = api_client.get(f"{BASE_URL}/api/booking/reviews/{TEST_PROPERTY_ID}?limit=6")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list), "Should return a list of reviews"
        print(f"Found {len(data)} reviews for booking engine display")


class TestBookingReservation:
    """Test booking reservation flow"""
    
    booking_ref = None
    room_type_id = None
    
    def test_create_booking_reservation(self, api_client):
        """POST /api/booking/reserve creates a booking and returns booking_ref"""
        # First get available rooms
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        day_after = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
        
        rooms_response = api_client.get(f"{BASE_URL}/api/booking/rooms/{TEST_PROPERTY_ID}")
        assert rooms_response.status_code == 200
        rooms = rooms_response.json()
        assert len(rooms) > 0, "Need at least one room type to test booking"
        
        # Use the first available room
        room = rooms[0]
        TestBookingReservation.room_type_id = room["id"]
        
        # Create booking
        booking_data = {
            "property_id": TEST_PROPERTY_ID,
            "room_type_id": room["id"],
            "guest_name": TEST_GUEST_NAME,
            "guest_email": TEST_GUEST_EMAIL,
            "guest_phone": "+44 7123 456789",
            "check_in": tomorrow,
            "check_out": day_after,
            "adults": 2,
            "children": 0,
            "rooms": 1,
            "special_requests": "Late check-in requested"
        }
        
        response = api_client.post(f"{BASE_URL}/api/booking/reserve", json=booking_data)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "booking_ref" in data, "Response should include booking_ref"
        assert data["booking_ref"].startswith("MHB-"), f"Booking ref should start with MHB-, got {data['booking_ref']}"
        assert data["guest_name"] == TEST_GUEST_NAME
        assert data["guest_email"] == TEST_GUEST_EMAIL
        assert data["status"] == "confirmed"
        assert "total_price" in data
        assert data["total_price"] > 0, "Total price should be calculated"
        
        TestBookingReservation.booking_ref = data["booking_ref"]
        print(f"Created booking: {data['booking_ref']}, total: £{data['total_price']}")
    
    def test_get_booking_by_ref(self, api_client):
        """GET /api/booking/reservation/{ref} returns booking details"""
        if not TestBookingReservation.booking_ref:
            pytest.skip("No booking ref from previous test")
        
        response = api_client.get(f"{BASE_URL}/api/booking/reservation/{TestBookingReservation.booking_ref}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["booking_ref"] == TestBookingReservation.booking_ref
        assert data["guest_name"] == TEST_GUEST_NAME
        assert "room_type" in data, "Should include room_type details"
        assert "property" in data, "Should include property details"
        print(f"Retrieved booking: {data['booking_ref']}")
    
    def test_get_booking_not_found(self, api_client):
        """GET /api/booking/reservation/{invalid_ref} returns 404"""
        response = api_client.get(f"{BASE_URL}/api/booking/reservation/MHB-INVALID123")
        assert response.status_code == 404
    
    def test_booking_reduces_availability(self, api_client):
        """Verify booking reduces available room count"""
        if not TestBookingReservation.room_type_id:
            pytest.skip("No room type id from previous test")
        
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        day_after = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
        
        response = api_client.get(
            f"{BASE_URL}/api/booking/rooms/{TEST_PROPERTY_ID}",
            params={"check_in": tomorrow, "check_out": day_after}
        )
        assert response.status_code == 200
        
        rooms = response.json()
        booked_room = next((r for r in rooms if r["id"] == TestBookingReservation.room_type_id), None)
        if booked_room:
            print(f"Room {booked_room['name']}: {booked_room['available_rooms']} available of {booked_room.get('total_rooms', 'N/A')} total")


class TestRoomTypesCRUD:
    """Test admin room types CRUD operations"""
    
    created_room_id = None
    
    def test_list_room_types(self, authenticated_client):
        """GET /api/room-types returns all room types"""
        response = authenticated_client.get(f"{BASE_URL}/api/room-types")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 5, "Should have at least 5 seeded room types"
        print(f"Found {len(data)} room types")
    
    def test_list_room_types_by_property(self, authenticated_client):
        """GET /api/room-types?property_id=aldgate-flats filters by property"""
        response = authenticated_client.get(f"{BASE_URL}/api/room-types?property_id={TEST_PROPERTY_ID}")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        for room in data:
            assert room.get("property_id") == TEST_PROPERTY_ID
        print(f"Found {len(data)} room types for {TEST_PROPERTY_ID}")
    
    def test_create_room_type(self, authenticated_client):
        """POST /api/room-types creates a new room type"""
        room_data = {
            "property_id": TEST_PROPERTY_ID,
            "name": "TEST_Budget Single Room",
            "description": "Test room for automated testing",
            "max_guests": 1,
            "bed_type": "single",
            "size_sqm": 12,
            "amenities": ["Free WiFi", "Air conditioning"],
            "photos": ["https://example.com/test-room.jpg"],
            "base_price": 59,
            "currency": "GBP",
            "total_rooms": 3,
            "free_cancellation": True,
            "breakfast_included": False
        }
        
        response = authenticated_client.post(f"{BASE_URL}/api/room-types", json=room_data)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "id" in data
        assert data["name"] == "TEST_Budget Single Room"
        assert data["base_price"] == 59
        
        TestRoomTypesCRUD.created_room_id = data["id"]
        print(f"Created room type: {data['id']}")
    
    def test_update_room_type(self, authenticated_client):
        """PUT /api/room-types/{id} updates a room type"""
        if not TestRoomTypesCRUD.created_room_id:
            pytest.skip("No room id from previous test")
        
        update_data = {
            "base_price": 69,
            "description": "Updated test room description"
        }
        
        response = authenticated_client.put(
            f"{BASE_URL}/api/room-types/{TestRoomTypesCRUD.created_room_id}",
            json=update_data
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["base_price"] == 69
        assert "Updated" in data["description"]
        print(f"Updated room type: {data['id']}")
    
    def test_delete_room_type(self, authenticated_client):
        """DELETE /api/room-types/{id} deletes a room type"""
        if not TestRoomTypesCRUD.created_room_id:
            pytest.skip("No room id from previous test")
        
        response = authenticated_client.delete(f"{BASE_URL}/api/room-types/{TestRoomTypesCRUD.created_room_id}")
        assert response.status_code == 200
        
        # Verify deletion
        get_response = authenticated_client.get(f"{BASE_URL}/api/room-types")
        rooms = get_response.json()
        deleted_room = next((r for r in rooms if r["id"] == TestRoomTypesCRUD.created_room_id), None)
        assert deleted_room is None, "Room should be deleted"
        print(f"Deleted room type: {TestRoomTypesCRUD.created_room_id}")


class TestBookingsManagement:
    """Test admin bookings management"""
    
    def test_list_bookings(self, authenticated_client):
        """GET /api/bookings returns all bookings"""
        response = authenticated_client.get(f"{BASE_URL}/api/bookings")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        print(f"Found {len(data)} bookings")
    
    def test_list_bookings_by_property(self, authenticated_client):
        """GET /api/bookings?property_id=aldgate-flats filters by property"""
        response = authenticated_client.get(f"{BASE_URL}/api/bookings?property_id={TEST_PROPERTY_ID}")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        for booking in data:
            assert booking.get("property_id") == TEST_PROPERTY_ID
    
    def test_update_booking_status_checkin(self, authenticated_client):
        """PUT /api/bookings/{id}/status?status=checked_in updates booking status"""
        # Get a confirmed booking
        response = authenticated_client.get(f"{BASE_URL}/api/bookings?status=confirmed")
        bookings = response.json()
        
        if not bookings:
            pytest.skip("No confirmed bookings to test status update")
        
        # Find our test booking
        test_booking = next((b for b in bookings if b.get("guest_name") == TEST_GUEST_NAME), None)
        if not test_booking:
            test_booking = bookings[0]
        
        booking_id = test_booking["id"]
        
        # Update to checked_in
        response = authenticated_client.put(f"{BASE_URL}/api/bookings/{booking_id}/status?status=checked_in")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "checked_in"
        print(f"Updated booking {booking_id} to checked_in")
    
    def test_update_booking_status_invalid(self, authenticated_client):
        """PUT /api/bookings/{id}/status with invalid status returns 400"""
        response = authenticated_client.get(f"{BASE_URL}/api/bookings")
        bookings = response.json()
        
        if not bookings:
            pytest.skip("No bookings to test")
        
        booking_id = bookings[0]["id"]
        response = authenticated_client.put(f"{BASE_URL}/api/bookings/{booking_id}/status?status=invalid_status")
        assert response.status_code == 400


class TestSeededRoomTypes:
    """Verify seeded room types exist and have correct structure"""
    
    def test_seeded_rooms_exist(self, api_client):
        """Verify 5 seeded room types exist for aldgate-flats"""
        response = api_client.get(f"{BASE_URL}/api/booking/rooms/{TEST_PROPERTY_ID}")
        assert response.status_code == 200
        
        rooms = response.json()
        assert len(rooms) >= 5, f"Expected at least 5 seeded rooms, got {len(rooms)}"
        
        # Check expected room names
        room_names = [r["name"] for r in rooms]
        expected_rooms = ["Standard Double Room", "Deluxe King Room", "Family Suite", "Superior Twin Room", "Executive Suite"]
        
        for expected in expected_rooms:
            assert any(expected in name for name in room_names), f"Missing expected room: {expected}"
        
        print(f"Verified {len(rooms)} seeded room types: {room_names}")
    
    def test_seeded_rooms_have_photos(self, api_client):
        """Verify seeded rooms have photo URLs"""
        response = api_client.get(f"{BASE_URL}/api/booking/rooms/{TEST_PROPERTY_ID}")
        rooms = response.json()
        
        for room in rooms:
            assert "photos" in room, f"Room {room['name']} missing photos field"
            if room.get("photos"):
                assert len(room["photos"]) > 0, f"Room {room['name']} has empty photos array"
                assert room["photos"][0].startswith("http"), f"Room {room['name']} photo URL invalid"
    
    def test_seeded_rooms_have_amenities(self, api_client):
        """Verify seeded rooms have amenities"""
        response = api_client.get(f"{BASE_URL}/api/booking/rooms/{TEST_PROPERTY_ID}")
        rooms = response.json()
        
        for room in rooms:
            assert "amenities" in room, f"Room {room['name']} missing amenities field"
            assert len(room.get("amenities", [])) > 0, f"Room {room['name']} has no amenities"
    
    def test_seeded_rooms_have_pricing(self, api_client):
        """Verify seeded rooms have pricing info"""
        response = api_client.get(f"{BASE_URL}/api/booking/rooms/{TEST_PROPERTY_ID}")
        rooms = response.json()
        
        for room in rooms:
            assert "base_price" in room, f"Room {room['name']} missing base_price"
            assert room["base_price"] > 0, f"Room {room['name']} has invalid price"
            assert "currency" in room, f"Room {room['name']} missing currency"
    
    def test_family_suite_has_limited_availability(self, api_client):
        """Verify Family Suite has only 2 rooms (for urgency cue testing)"""
        response = api_client.get(f"{BASE_URL}/api/booking/rooms/{TEST_PROPERTY_ID}")
        rooms = response.json()
        
        family_suite = next((r for r in rooms if "Family" in r["name"]), None)
        if family_suite:
            assert family_suite.get("total_rooms", 0) <= 3, "Family Suite should have limited rooms for urgency cue"
            print(f"Family Suite has {family_suite.get('total_rooms')} total rooms")


class TestCleanup:
    """Cleanup test data"""
    
    def test_cleanup_test_bookings(self, authenticated_client):
        """Cancel test bookings created during testing"""
        response = authenticated_client.get(f"{BASE_URL}/api/bookings")
        bookings = response.json()
        
        test_bookings = [b for b in bookings if b.get("guest_name", "").startswith("TEST_")]
        
        for booking in test_bookings:
            cancel_response = authenticated_client.put(
                f"{BASE_URL}/api/bookings/{booking['id']}/status?status=cancelled"
            )
            if cancel_response.status_code == 200:
                print(f"Cancelled test booking: {booking['booking_ref']}")
        
        print(f"Cleaned up {len(test_bookings)} test bookings")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
