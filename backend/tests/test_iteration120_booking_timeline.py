"""
Iteration 120 - Booking Timeline (Gantt-style Calendar) API Tests
Tests for:
- GET /api/bookings/timeline/{property_id} - Timeline data with rooms and bookings
- GET /api/bookings/timeline/{property_id}/detail/{booking_id} - Booking detail
- PUT /api/bookings/timeline/{property_id}/status/{booking_id} - Update booking status
- Auto-seeding of rooms and bookings for properties with room types
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestBookingTimelineAuth:
    """Authentication for timeline tests"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        """Get authenticated session"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        return session
    
    def test_login_success(self, auth_session):
        """Verify admin login works"""
        response = auth_session.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "admin@hotelbox.com"
        print(f"✓ Logged in as: {data['name']} ({data['role']})")


class TestBookingTimelineAPI:
    """Booking Timeline API endpoint tests"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        """Get authenticated session"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        login_response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_response.status_code == 200
        return session
    
    @pytest.fixture(scope="class")
    def property_id(self, auth_session):
        """Get a property ID with room types"""
        # First get properties
        response = auth_session.get(f"{BASE_URL}/api/properties")
        assert response.status_code == 200
        properties = response.json()
        
        # Find aldgate-flats or first property with room types
        for prop in properties:
            if prop.get("id") == "aldgate-flats":
                return prop["id"]
        
        # Fallback to first property
        if properties:
            return properties[0].get("id", "all")
        return "all"
    
    def test_timeline_endpoint_returns_200(self, auth_session, property_id):
        """Test timeline endpoint returns 200 with valid structure"""
        response = auth_session.get(f"{BASE_URL}/api/bookings/timeline/{property_id}?days=14")
        assert response.status_code == 200, f"Timeline failed: {response.text}"
        data = response.json()
        
        # Verify required fields
        assert "property_id" in data
        assert "date_columns" in data
        assert "daily_occupancy" in data
        assert "groups" in data
        assert "total_rooms" in data
        assert "total_bookings" in data
        assert "start" in data
        assert "end" in data
        assert "days" in data
        
        print(f"✓ Timeline returned: {data['total_rooms']} rooms, {data['total_bookings']} bookings")
    
    def test_timeline_date_columns_structure(self, auth_session, property_id):
        """Test date_columns have correct structure"""
        response = auth_session.get(f"{BASE_URL}/api/bookings/timeline/{property_id}?days=7")
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["date_columns"]) == 7, "Should have 7 date columns for 7 days"
        
        # Check first column structure
        col = data["date_columns"][0]
        assert "date" in col
        assert "day" in col
        assert "dow" in col  # Day of week
        assert "month" in col
        assert "is_today" in col
        assert "is_weekend" in col
        
        print(f"✓ Date columns: {[c['date'] for c in data['date_columns'][:3]]}...")
    
    def test_timeline_daily_occupancy_structure(self, auth_session, property_id):
        """Test daily_occupancy has correct structure"""
        response = auth_session.get(f"{BASE_URL}/api/bookings/timeline/{property_id}?days=14")
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["daily_occupancy"]) == 14, "Should have 14 occupancy entries"
        
        # Check first occupancy entry
        occ = data["daily_occupancy"][0]
        assert "date" in occ
        assert "booked" in occ
        assert "available" in occ
        assert "occupancy_pct" in occ
        
        print(f"✓ Daily occupancy sample: {occ['date']} - {occ['occupancy_pct']}% occupied")
    
    def test_timeline_groups_structure(self, auth_session, property_id):
        """Test groups (room types) have correct structure"""
        response = auth_session.get(f"{BASE_URL}/api/bookings/timeline/{property_id}?days=14")
        assert response.status_code == 200
        data = response.json()
        
        if len(data["groups"]) > 0:
            group = data["groups"][0]
            assert "room_type_id" in group
            assert "room_type_name" in group
            assert "rate" in group
            assert "total_rooms" in group
            assert "rooms" in group
            
            print(f"✓ Room type groups: {[g['room_type_name'] for g in data['groups']]}")
            
            # Check room structure
            if len(group["rooms"]) > 0:
                room = group["rooms"][0]
                assert "id" in room
                assert "name" in room
                assert "floor" in room
                assert "status" in room
                assert "housekeeping" in room
                assert "bookings" in room
                
                print(f"✓ Sample room: {room['name']} (Floor {room['floor']})")
    
    def test_timeline_booking_bar_structure(self, auth_session, property_id):
        """Test booking bars have correct structure"""
        response = auth_session.get(f"{BASE_URL}/api/bookings/timeline/{property_id}?days=14")
        assert response.status_code == 200
        data = response.json()
        
        # Find a booking
        booking = None
        for group in data["groups"]:
            for room in group["rooms"]:
                if room["bookings"]:
                    booking = room["bookings"][0]
                    break
            if booking:
                break
        
        if booking:
            assert "id" in booking
            assert "guest_name" in booking
            assert "check_in" in booking
            assert "check_out" in booking
            assert "nights" in booking
            assert "status" in booking
            assert "source" in booking
            assert "source_code" in booking
            assert "total_price" in booking
            assert "rate_per_night" in booking
            assert "adults" in booking
            assert "payment_status" in booking
            
            print(f"✓ Sample booking: {booking['guest_name']} ({booking['check_in']} to {booking['check_out']}) - {booking['status']}")
        else:
            print("⚠ No bookings found in timeline")
    
    def test_timeline_view_days_7(self, auth_session, property_id):
        """Test 7-day view"""
        response = auth_session.get(f"{BASE_URL}/api/bookings/timeline/{property_id}?days=7")
        assert response.status_code == 200
        data = response.json()
        assert data["days"] == 7
        assert len(data["date_columns"]) == 7
        print("✓ 7-day view works correctly")
    
    def test_timeline_view_days_30(self, auth_session, property_id):
        """Test 30-day view"""
        response = auth_session.get(f"{BASE_URL}/api/bookings/timeline/{property_id}?days=30")
        assert response.status_code == 200
        data = response.json()
        assert data["days"] == 30
        assert len(data["date_columns"]) == 30
        print("✓ 30-day view works correctly")
    
    def test_timeline_with_start_date(self, auth_session, property_id):
        """Test timeline with custom start date"""
        response = auth_session.get(f"{BASE_URL}/api/bookings/timeline/{property_id}?start=2026-01-15&days=14")
        assert response.status_code == 200
        data = response.json()
        assert data["start"] == "2026-01-15"
        print(f"✓ Custom start date: {data['start']} to {data['end']}")
    
    def test_timeline_all_properties(self, auth_session):
        """Test timeline with 'all' property_id picks first property with room types"""
        response = auth_session.get(f"{BASE_URL}/api/bookings/timeline/all?days=14")
        assert response.status_code == 200
        data = response.json()
        assert data["property_id"] != "all", "Should resolve to actual property ID"
        print(f"✓ 'all' resolved to property: {data['property_id']}")


class TestBookingDetailAPI:
    """Booking detail endpoint tests"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        """Get authenticated session"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        login_response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_response.status_code == 200
        return session
    
    @pytest.fixture(scope="class")
    def booking_data(self, auth_session):
        """Get a booking ID from timeline"""
        response = auth_session.get(f"{BASE_URL}/api/bookings/timeline/all?days=14")
        assert response.status_code == 200
        data = response.json()
        
        # Find a booking
        for group in data["groups"]:
            for room in group["rooms"]:
                if room["bookings"]:
                    return {
                        "property_id": data["property_id"],
                        "booking_id": room["bookings"][0]["id"]
                    }
        
        pytest.skip("No bookings found for detail test")
    
    def test_booking_detail_returns_200(self, auth_session, booking_data):
        """Test booking detail endpoint returns 200"""
        response = auth_session.get(
            f"{BASE_URL}/api/bookings/timeline/{booking_data['property_id']}/detail/{booking_data['booking_id']}"
        )
        assert response.status_code == 200, f"Detail failed: {response.text}"
        data = response.json()
        
        # Verify required fields
        assert "id" in data
        assert "guest_name" in data
        assert "check_in" in data
        assert "check_out" in data
        assert "status" in data
        
        print(f"✓ Booking detail: {data['guest_name']} - {data['status']}")
    
    def test_booking_detail_includes_room_info(self, auth_session, booking_data):
        """Test booking detail includes room information"""
        response = auth_session.get(
            f"{BASE_URL}/api/bookings/timeline/{booking_data['property_id']}/detail/{booking_data['booking_id']}"
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check room info fields
        assert "room_name" in data
        assert "room_type_name" in data
        
        print(f"✓ Room info: {data.get('room_type_name')} - {data.get('room_name')}")
    
    def test_booking_detail_includes_guest_info(self, auth_session, booking_data):
        """Test booking detail includes guest information"""
        response = auth_session.get(
            f"{BASE_URL}/api/bookings/timeline/{booking_data['property_id']}/detail/{booking_data['booking_id']}"
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check guest info fields
        assert "guest_name" in data
        assert "guest_email" in data or data.get("guest_email") is None
        assert "adults" in data
        
        print(f"✓ Guest info: {data['guest_name']}, {data.get('adults', 1)} adults")
    
    def test_booking_detail_includes_financial_info(self, auth_session, booking_data):
        """Test booking detail includes financial information"""
        response = auth_session.get(
            f"{BASE_URL}/api/bookings/timeline/{booking_data['property_id']}/detail/{booking_data['booking_id']}"
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check financial fields
        assert "total_price" in data
        assert "rate_per_night" in data
        assert "payment_status" in data
        
        print(f"✓ Financial: £{data.get('total_price', 0)} total, £{data.get('rate_per_night', 0)}/night")
    
    def test_booking_detail_not_found(self, auth_session, booking_data):
        """Test booking detail returns error for non-existent booking"""
        response = auth_session.get(
            f"{BASE_URL}/api/bookings/timeline/{booking_data['property_id']}/detail/non-existent-id"
        )
        assert response.status_code == 200  # Returns 200 with error field
        data = response.json()
        assert "error" in data
        print("✓ Non-existent booking returns error")


class TestBookingStatusAPI:
    """Booking status update endpoint tests"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        """Get authenticated session"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        login_response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_response.status_code == 200
        return session
    
    @pytest.fixture(scope="class")
    def test_booking(self, auth_session):
        """Get a booking for status tests"""
        response = auth_session.get(f"{BASE_URL}/api/bookings/timeline/all?days=14")
        assert response.status_code == 200
        data = response.json()
        
        # Find a pending or confirmed booking
        for group in data["groups"]:
            for room in group["rooms"]:
                for booking in room["bookings"]:
                    if booking["status"] in ["pending", "confirmed"]:
                        return {
                            "property_id": data["property_id"],
                            "booking_id": booking["id"],
                            "original_status": booking["status"]
                        }
        
        # Fallback to any booking
        for group in data["groups"]:
            for room in group["rooms"]:
                if room["bookings"]:
                    return {
                        "property_id": data["property_id"],
                        "booking_id": room["bookings"][0]["id"],
                        "original_status": room["bookings"][0]["status"]
                    }
        
        pytest.skip("No bookings found for status test")
    
    def test_update_status_to_confirmed(self, auth_session, test_booking):
        """Test updating booking status to confirmed"""
        response = auth_session.put(
            f"{BASE_URL}/api/bookings/timeline/{test_booking['property_id']}/status/{test_booking['booking_id']}",
            json={"status": "confirmed"}
        )
        assert response.status_code == 200, f"Status update failed: {response.text}"
        data = response.json()
        assert data["status"] == "confirmed"
        assert data["booking_id"] == test_booking["booking_id"]
        print("✓ Status updated to confirmed")
    
    def test_update_status_to_checked_in(self, auth_session, test_booking):
        """Test updating booking status to checked_in"""
        response = auth_session.put(
            f"{BASE_URL}/api/bookings/timeline/{test_booking['property_id']}/status/{test_booking['booking_id']}",
            json={"status": "checked_in"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "checked_in"
        print("✓ Status updated to checked_in")
    
    def test_update_status_to_checked_out(self, auth_session, test_booking):
        """Test updating booking status to checked_out"""
        response = auth_session.put(
            f"{BASE_URL}/api/bookings/timeline/{test_booking['property_id']}/status/{test_booking['booking_id']}",
            json={"status": "checked_out"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "checked_out"
        print("✓ Status updated to checked_out")
    
    def test_update_status_invalid(self, auth_session, test_booking):
        """Test updating booking status with invalid status"""
        response = auth_session.put(
            f"{BASE_URL}/api/bookings/timeline/{test_booking['property_id']}/status/{test_booking['booking_id']}",
            json={"status": "invalid_status"}
        )
        assert response.status_code == 200  # Returns 200 with error
        data = response.json()
        assert "error" in data
        print("✓ Invalid status returns error")
    
    def test_status_change_persists(self, auth_session, test_booking):
        """Test that status change persists in database"""
        # Set to pending
        auth_session.put(
            f"{BASE_URL}/api/bookings/timeline/{test_booking['property_id']}/status/{test_booking['booking_id']}",
            json={"status": "pending"}
        )
        
        # Verify via detail endpoint
        response = auth_session.get(
            f"{BASE_URL}/api/bookings/timeline/{test_booking['property_id']}/detail/{test_booking['booking_id']}"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"
        print("✓ Status change persisted in database")
        
        # Restore original status
        auth_session.put(
            f"{BASE_URL}/api/bookings/timeline/{test_booking['property_id']}/status/{test_booking['booking_id']}",
            json={"status": test_booking["original_status"]}
        )


class TestAutoSeedingBehavior:
    """Test auto-seeding of rooms and bookings"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        """Get authenticated session"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        login_response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_response.status_code == 200
        return session
    
    def test_timeline_has_rooms_after_seed(self, auth_session):
        """Test that timeline has rooms (auto-seeded if needed)"""
        response = auth_session.get(f"{BASE_URL}/api/bookings/timeline/all?days=14")
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_rooms"] > 0, "Should have rooms after auto-seed"
        print(f"✓ Timeline has {data['total_rooms']} rooms")
    
    def test_timeline_has_bookings_after_seed(self, auth_session):
        """Test that timeline has bookings (auto-seeded if needed)"""
        response = auth_session.get(f"{BASE_URL}/api/bookings/timeline/all?days=14")
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_bookings"] > 0, "Should have bookings after auto-seed"
        print(f"✓ Timeline has {data['total_bookings']} bookings")
    
    def test_rooms_have_valid_room_types(self, auth_session):
        """Test that rooms are assigned to valid room types"""
        response = auth_session.get(f"{BASE_URL}/api/bookings/timeline/all?days=14")
        assert response.status_code == 200
        data = response.json()
        
        for group in data["groups"]:
            assert group["room_type_id"], "Room type should have ID"
            assert group["room_type_name"], "Room type should have name"
            assert group["total_rooms"] >= 0, "Should have room count"
            
            for room in group["rooms"]:
                assert room["id"], "Room should have ID"
                assert room["name"], "Room should have name"
        
        print(f"✓ All {len(data['groups'])} room type groups have valid structure")
    
    def test_bookings_have_valid_statuses(self, auth_session):
        """Test that bookings have valid status values"""
        valid_statuses = ["pending", "confirmed", "checked_in", "checked_out", "no_show", "cancelled"]
        
        response = auth_session.get(f"{BASE_URL}/api/bookings/timeline/all?days=14")
        assert response.status_code == 200
        data = response.json()
        
        status_counts = {}
        for group in data["groups"]:
            for room in group["rooms"]:
                for booking in room["bookings"]:
                    status = booking["status"]
                    assert status in valid_statuses, f"Invalid status: {status}"
                    status_counts[status] = status_counts.get(status, 0) + 1
        
        print(f"✓ Booking status distribution: {status_counts}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
