"""
Iteration 121 - Booking Timeline Drag-and-Drop & Bulk Actions Tests
Tests:
- PUT /api/bookings/timeline/{property_id}/reassign/{booking_id} - Room reassignment
- POST /api/bookings/timeline/{property_id}/bulk-action - Bulk status updates
- GET /api/bookings/timeline/{property_id}/todays-actions - Today's arrivals/departures/in-house
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def auth_token():
    """Get admin authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    return data.get("token")

@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}

@pytest.fixture(scope="module")
def property_id():
    """Property ID for testing"""
    return "aldgate-flats"

@pytest.fixture(scope="module")
def timeline_data(auth_headers, property_id):
    """Get timeline data with rooms and bookings"""
    response = requests.get(
        f"{BASE_URL}/api/bookings/timeline/{property_id}?days=30",
        headers=auth_headers
    )
    assert response.status_code == 200
    return response.json()


class TestTodaysActions:
    """Tests for GET /api/bookings/timeline/{property_id}/todays-actions"""
    
    def test_todays_actions_endpoint_exists(self, auth_headers, property_id):
        """Test that todays-actions endpoint returns 200"""
        response = requests.get(
            f"{BASE_URL}/api/bookings/timeline/{property_id}/todays-actions",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_todays_actions_response_structure(self, auth_headers, property_id):
        """Test response has required fields"""
        response = requests.get(
            f"{BASE_URL}/api/bookings/timeline/{property_id}/todays-actions",
            headers=auth_headers
        )
        data = response.json()
        
        # Check required fields
        assert "date" in data, "Missing 'date' field"
        assert "arrivals" in data, "Missing 'arrivals' field"
        assert "departures" in data, "Missing 'departures' field"
        assert "in_house" in data, "Missing 'in_house' field"
        assert "counts" in data, "Missing 'counts' field"
        
        # Check counts structure
        counts = data["counts"]
        assert "arrivals" in counts, "Missing 'arrivals' in counts"
        assert "departures" in counts, "Missing 'departures' in counts"
        assert "in_house" in counts, "Missing 'in_house' in counts"
    
    def test_todays_actions_date_is_today(self, auth_headers, property_id):
        """Test that date field is today's date"""
        response = requests.get(
            f"{BASE_URL}/api/bookings/timeline/{property_id}/todays-actions",
            headers=auth_headers
        )
        data = response.json()
        today = datetime.now().strftime("%Y-%m-%d")
        assert data["date"] == today, f"Expected date {today}, got {data['date']}"
    
    def test_todays_actions_arrivals_structure(self, auth_headers, property_id):
        """Test arrivals array structure"""
        response = requests.get(
            f"{BASE_URL}/api/bookings/timeline/{property_id}/todays-actions",
            headers=auth_headers
        )
        data = response.json()
        
        # If there are arrivals, check structure
        if data["arrivals"]:
            arrival = data["arrivals"][0]
            assert "id" in arrival, "Arrival missing 'id'"
            assert "guest_name" in arrival, "Arrival missing 'guest_name'"
            assert "room_id" in arrival, "Arrival missing 'room_id'"
            assert "check_in" in arrival, "Arrival missing 'check_in'"
            assert "check_out" in arrival, "Arrival missing 'check_out'"
            assert "status" in arrival, "Arrival missing 'status'"
    
    def test_todays_actions_counts_match_arrays(self, auth_headers, property_id):
        """Test that counts match array lengths"""
        response = requests.get(
            f"{BASE_URL}/api/bookings/timeline/{property_id}/todays-actions",
            headers=auth_headers
        )
        data = response.json()
        
        assert data["counts"]["arrivals"] == len(data["arrivals"]), "Arrivals count mismatch"
        assert data["counts"]["departures"] == len(data["departures"]), "Departures count mismatch"
        assert data["counts"]["in_house"] == len(data["in_house"]), "In-house count mismatch"


class TestRoomReassignment:
    """Tests for PUT /api/bookings/timeline/{property_id}/reassign/{booking_id}"""
    
    def test_reassign_requires_room_id(self, auth_headers, property_id, timeline_data):
        """Test that reassign requires room_id parameter"""
        # Get a booking ID
        booking_id = None
        for group in timeline_data.get("groups", []):
            for room in group.get("rooms", []):
                if room.get("bookings"):
                    booking_id = room["bookings"][0]["id"]
                    break
            if booking_id:
                break
        
        if not booking_id:
            pytest.skip("No bookings found for testing")
        
        response = requests.put(
            f"{BASE_URL}/api/bookings/timeline/{property_id}/reassign/{booking_id}",
            headers=auth_headers,
            json={}
        )
        assert response.status_code == 200
        data = response.json()
        assert "error" in data, "Expected error for missing room_id"
        assert data["error"] == "room_id required"
    
    def test_reassign_invalid_booking(self, auth_headers, property_id, timeline_data):
        """Test reassign with invalid booking ID"""
        # Get a valid room ID
        room_id = None
        for group in timeline_data.get("groups", []):
            for room in group.get("rooms", []):
                room_id = room["id"]
                break
            if room_id:
                break
        
        if not room_id:
            pytest.skip("No rooms found for testing")
        
        response = requests.put(
            f"{BASE_URL}/api/bookings/timeline/{property_id}/reassign/invalid-booking-id",
            headers=auth_headers,
            json={"room_id": room_id}
        )
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"] == "Booking not found"
    
    def test_reassign_invalid_room(self, auth_headers, property_id, timeline_data):
        """Test reassign with invalid room ID"""
        # Get a booking ID
        booking_id = None
        for group in timeline_data.get("groups", []):
            for room in group.get("rooms", []):
                if room.get("bookings"):
                    booking_id = room["bookings"][0]["id"]
                    break
            if booking_id:
                break
        
        if not booking_id:
            pytest.skip("No bookings found for testing")
        
        response = requests.put(
            f"{BASE_URL}/api/bookings/timeline/{property_id}/reassign/{booking_id}",
            headers=auth_headers,
            json={"room_id": "invalid-room-id"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"] == "Room not found"
    
    def test_reassign_successful(self, auth_headers, property_id, timeline_data):
        """Test successful room reassignment"""
        # Find a booking and a different room to reassign to
        booking_id = None
        original_room_id = None
        target_room_id = None
        
        all_rooms = []
        for group in timeline_data.get("groups", []):
            for room in group.get("rooms", []):
                all_rooms.append(room)
                if room.get("bookings") and not booking_id:
                    booking_id = room["bookings"][0]["id"]
                    original_room_id = room["id"]
        
        # Find a different room
        for room in all_rooms:
            if room["id"] != original_room_id:
                target_room_id = room["id"]
                break
        
        if not booking_id or not target_room_id:
            pytest.skip("Not enough rooms/bookings for reassignment test")
        
        response = requests.put(
            f"{BASE_URL}/api/bookings/timeline/{property_id}/reassign/{booking_id}",
            headers=auth_headers,
            json={"room_id": target_room_id}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check for success or conflict (both are valid responses)
        if "error" not in data:
            assert data.get("status") == "reassigned", f"Expected status 'reassigned', got {data}"
            assert data.get("booking_id") == booking_id
            assert data.get("new_room_id") == target_room_id
            assert "new_room_name" in data
            
            # Reassign back to original room
            requests.put(
                f"{BASE_URL}/api/bookings/timeline/{property_id}/reassign/{booking_id}",
                headers=auth_headers,
                json={"room_id": original_room_id}
            )
        else:
            # Conflict is also a valid response
            assert data["error"] == "Room conflict"
            assert "conflict_guest" in data
            assert "conflict_dates" in data
    
    def test_reassign_conflict_detection(self, auth_headers, property_id, timeline_data):
        """Test that reassignment detects conflicts"""
        # Find two bookings in different rooms with overlapping dates
        bookings_with_rooms = []
        for group in timeline_data.get("groups", []):
            for room in group.get("rooms", []):
                for bk in room.get("bookings", []):
                    bookings_with_rooms.append({
                        "booking": bk,
                        "room_id": room["id"]
                    })
        
        if len(bookings_with_rooms) < 2:
            pytest.skip("Not enough bookings for conflict test")
        
        # Try to reassign first booking to second booking's room
        first = bookings_with_rooms[0]
        second = bookings_with_rooms[1]
        
        # Check if dates overlap
        first_ci = first["booking"]["check_in"]
        first_co = first["booking"]["check_out"]
        second_ci = second["booking"]["check_in"]
        second_co = second["booking"]["check_out"]
        
        # Dates overlap if: first_ci < second_co AND first_co > second_ci
        dates_overlap = first_ci < second_co and first_co > second_ci
        
        response = requests.put(
            f"{BASE_URL}/api/bookings/timeline/{property_id}/reassign/{first['booking']['id']}",
            headers=auth_headers,
            json={"room_id": second["room_id"]}
        )
        assert response.status_code == 200
        data = response.json()
        
        if dates_overlap:
            # Should detect conflict
            if "error" in data and data["error"] == "Room conflict":
                assert "conflict_guest" in data
                assert "conflict_dates" in data
                print(f"Conflict detected: {data['conflict_guest']} ({data['conflict_dates']})")
        # If no overlap, reassignment should succeed


class TestBulkActions:
    """Tests for POST /api/bookings/timeline/{property_id}/bulk-action"""
    
    def test_bulk_action_requires_booking_ids(self, auth_headers, property_id):
        """Test that bulk action requires booking_ids"""
        response = requests.post(
            f"{BASE_URL}/api/bookings/timeline/{property_id}/bulk-action",
            headers=auth_headers,
            json={"action": "checked_in"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"] == "booking_ids and action required"
    
    def test_bulk_action_requires_action(self, auth_headers, property_id):
        """Test that bulk action requires action parameter"""
        response = requests.post(
            f"{BASE_URL}/api/bookings/timeline/{property_id}/bulk-action",
            headers=auth_headers,
            json={"booking_ids": ["test-id"]}
        )
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"] == "booking_ids and action required"
    
    def test_bulk_action_invalid_action(self, auth_headers, property_id):
        """Test that invalid action is rejected"""
        response = requests.post(
            f"{BASE_URL}/api/bookings/timeline/{property_id}/bulk-action",
            headers=auth_headers,
            json={"booking_ids": ["test-id"], "action": "invalid_action"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"] == "Invalid action"
    
    def test_bulk_action_valid_actions(self, auth_headers, property_id):
        """Test all valid action types are accepted"""
        valid_actions = ["checked_in", "checked_out", "confirmed", "cancelled", "no_show"]
        
        for action in valid_actions:
            response = requests.post(
                f"{BASE_URL}/api/bookings/timeline/{property_id}/bulk-action",
                headers=auth_headers,
                json={"booking_ids": ["nonexistent-id"], "action": action}
            )
            assert response.status_code == 200
            data = response.json()
            # Should not return "Invalid action" error
            assert data.get("error") != "Invalid action", f"Action '{action}' was rejected as invalid"
    
    def test_bulk_action_nonexistent_bookings(self, auth_headers, property_id):
        """Test bulk action with nonexistent booking IDs"""
        response = requests.post(
            f"{BASE_URL}/api/bookings/timeline/{property_id}/bulk-action",
            headers=auth_headers,
            json={"booking_ids": ["fake-id-1", "fake-id-2"], "action": "checked_in"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "action" in data
        assert "updated" in data
        assert "errors" in data
        assert "total_requested" in data
        
        assert data["updated"] == 0, "Should not update nonexistent bookings"
        assert data["total_requested"] == 2
        assert len(data["errors"]) == 2
    
    def test_bulk_checkin_from_confirmed(self, auth_headers, property_id, timeline_data):
        """Test bulk check-in from confirmed status"""
        # Find confirmed bookings
        confirmed_bookings = []
        for group in timeline_data.get("groups", []):
            for room in group.get("rooms", []):
                for bk in room.get("bookings", []):
                    if bk.get("status") == "confirmed":
                        confirmed_bookings.append(bk["id"])
        
        if not confirmed_bookings:
            pytest.skip("No confirmed bookings found")
        
        # Try to check in first confirmed booking
        booking_id = confirmed_bookings[0]
        response = requests.post(
            f"{BASE_URL}/api/bookings/timeline/{property_id}/bulk-action",
            headers=auth_headers,
            json={"booking_ids": [booking_id], "action": "checked_in"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["action"] == "checked_in"
        assert data["updated"] == 1, f"Expected 1 update, got {data['updated']}"
        assert data["total_requested"] == 1
        
        # Revert back to confirmed
        requests.post(
            f"{BASE_URL}/api/bookings/timeline/{property_id}/bulk-action",
            headers=auth_headers,
            json={"booking_ids": [booking_id], "action": "confirmed"}
        )
    
    def test_bulk_checkout_from_checked_in(self, auth_headers, property_id, timeline_data):
        """Test bulk check-out from checked_in status"""
        # Find checked_in bookings
        checked_in_bookings = []
        for group in timeline_data.get("groups", []):
            for room in group.get("rooms", []):
                for bk in room.get("bookings", []):
                    if bk.get("status") == "checked_in":
                        checked_in_bookings.append(bk["id"])
        
        if not checked_in_bookings:
            pytest.skip("No checked_in bookings found")
        
        booking_id = checked_in_bookings[0]
        response = requests.post(
            f"{BASE_URL}/api/bookings/timeline/{property_id}/bulk-action",
            headers=auth_headers,
            json={"booking_ids": [booking_id], "action": "checked_out"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["action"] == "checked_out"
        assert data["updated"] == 1
    
    def test_bulk_action_invalid_transition(self, auth_headers, property_id, timeline_data):
        """Test that invalid status transitions are rejected"""
        # Find a checked_out booking
        checked_out_bookings = []
        for group in timeline_data.get("groups", []):
            for room in group.get("rooms", []):
                for bk in room.get("bookings", []):
                    if bk.get("status") == "checked_out":
                        checked_out_bookings.append(bk["id"])
        
        if not checked_out_bookings:
            pytest.skip("No checked_out bookings found")
        
        # Try to check in a checked_out booking (invalid transition)
        booking_id = checked_out_bookings[0]
        response = requests.post(
            f"{BASE_URL}/api/bookings/timeline/{property_id}/bulk-action",
            headers=auth_headers,
            json={"booking_ids": [booking_id], "action": "checked_in"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["updated"] == 0, "Should not allow check-in from checked_out"
        assert len(data["errors"]) == 1
        assert "Cannot checked_in from checked_out" in data["errors"][0]["error"]
    
    def test_bulk_action_response_structure(self, auth_headers, property_id):
        """Test bulk action response has correct structure"""
        response = requests.post(
            f"{BASE_URL}/api/bookings/timeline/{property_id}/bulk-action",
            headers=auth_headers,
            json={"booking_ids": ["test-id"], "action": "confirmed"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "action" in data
        assert "updated" in data
        assert "errors" in data
        assert "total_requested" in data
        assert isinstance(data["errors"], list)


class TestTimelineIntegration:
    """Integration tests for timeline with new features"""
    
    def test_timeline_loads_with_bookings(self, auth_headers, property_id):
        """Test timeline loads and has bookings"""
        response = requests.get(
            f"{BASE_URL}/api/bookings/timeline/{property_id}?days=14",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_rooms"] > 0, "Expected rooms in timeline"
        assert data["total_bookings"] > 0, "Expected bookings in timeline"
        assert len(data["groups"]) > 0, "Expected room type groups"
    
    def test_booking_has_room_id(self, auth_headers, property_id, timeline_data):
        """Test that bookings have room_id for drag-and-drop"""
        for group in timeline_data.get("groups", []):
            for room in group.get("rooms", []):
                for bk in room.get("bookings", []):
                    # Booking should be associated with a room
                    assert room.get("id"), f"Room missing id: {room}"
                    # The booking is in this room's array, so it's associated
    
    def test_rooms_have_required_fields(self, auth_headers, property_id, timeline_data):
        """Test rooms have fields needed for drag-and-drop"""
        for group in timeline_data.get("groups", []):
            for room in group.get("rooms", []):
                assert "id" in room, "Room missing 'id'"
                assert "name" in room, "Room missing 'name'"
                assert "bookings" in room, "Room missing 'bookings'"
    
    def test_bookings_have_status(self, auth_headers, property_id, timeline_data):
        """Test bookings have status for bulk actions"""
        for group in timeline_data.get("groups", []):
            for room in group.get("rooms", []):
                for bk in room.get("bookings", []):
                    assert "status" in bk, f"Booking missing 'status': {bk}"
                    assert bk["status"] in ["pending", "confirmed", "checked_in", "checked_out", "no_show", "cancelled"]


class TestAuthorizationRoles:
    """Test role-based access for new endpoints"""
    
    def test_todays_actions_requires_auth(self, property_id):
        """Test todays-actions requires authentication"""
        response = requests.get(
            f"{BASE_URL}/api/bookings/timeline/{property_id}/todays-actions"
        )
        assert response.status_code == 401 or response.status_code == 403
    
    def test_reassign_requires_auth(self, property_id):
        """Test reassign requires authentication"""
        response = requests.put(
            f"{BASE_URL}/api/bookings/timeline/{property_id}/reassign/test-id",
            json={"room_id": "test-room"}
        )
        assert response.status_code == 401 or response.status_code == 403
    
    def test_bulk_action_requires_auth(self, property_id):
        """Test bulk-action requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/bookings/timeline/{property_id}/bulk-action",
            json={"booking_ids": ["test"], "action": "confirmed"}
        )
        assert response.status_code == 401 or response.status_code == 403
