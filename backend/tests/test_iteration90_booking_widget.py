"""
Iteration 90 - Premium Booking Widget API Tests
Tests the public booking engine APIs:
- GET /api/booking-widget/info/{property_id} - Hotel and room info
- POST /api/booking-widget/check-availability - Room availability check
- POST /api/booking-widget/book - Create booking
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestBookingWidgetInfo:
    """Tests for GET /api/booking-widget/info/{property_id}"""
    
    def test_get_hotel_info_success(self):
        """Test getting hotel info for vilenza-hotel"""
        response = requests.get(f"{BASE_URL}/api/booking-widget/info/vilenza-hotel")
        assert response.status_code == 200
        
        data = response.json()
        assert "hotel_name" in data
        assert "property_id" in data
        assert "rooms" in data
        assert "currency" in data
        
        # Verify hotel name
        assert data["hotel_name"] == "VILENZA HOTEL"
        assert data["property_id"] == "vilenza-hotel"
        assert data["currency"] == "GBP"
        
        # Verify rooms array
        assert isinstance(data["rooms"], list)
        assert len(data["rooms"]) >= 1
        print(f"✓ Hotel info returned: {data['hotel_name']} with {len(data['rooms'])} room types")
    
    def test_hotel_info_room_structure(self):
        """Test room data structure in hotel info"""
        response = requests.get(f"{BASE_URL}/api/booking-widget/info/vilenza-hotel")
        assert response.status_code == 200
        
        data = response.json()
        rooms = data["rooms"]
        
        for room in rooms:
            assert "id" in room
            assert "name" in room
            assert "base_rate" in room
            assert "max_occupancy" in room
            assert "description" in room
            print(f"  - Room: {room['name']} (ID: {room['id']})")
        
        print(f"✓ All {len(rooms)} rooms have correct structure")
    
    def test_hotel_info_nonexistent_property(self):
        """Test getting info for non-existent property returns fallback data"""
        response = requests.get(f"{BASE_URL}/api/booking-widget/info/nonexistent-hotel-xyz")
        # Should return 200 with fallback data (not 404)
        assert response.status_code == 200
        
        data = response.json()
        assert "hotel_name" in data
        assert "rooms" in data
        print(f"✓ Non-existent property returns fallback: {data['hotel_name']}")


class TestBookingWidgetAvailability:
    """Tests for POST /api/booking-widget/check-availability"""
    
    def test_check_availability_success(self):
        """Test checking room availability"""
        payload = {
            "property_id": "vilenza-hotel",
            "check_in": "2026-02-01",
            "check_out": "2026-02-03"
        }
        response = requests.post(f"{BASE_URL}/api/booking-widget/check-availability", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert "available_rooms" in data
        assert "check_in" in data
        assert "check_out" in data
        
        assert data["check_in"] == "2026-02-01"
        assert data["check_out"] == "2026-02-03"
        
        rooms = data["available_rooms"]
        assert isinstance(rooms, list)
        print(f"✓ Availability check returned {len(rooms)} available rooms")
    
    def test_availability_room_pricing(self):
        """Test that availability returns correct pricing"""
        payload = {
            "property_id": "vilenza-hotel",
            "check_in": "2026-02-01",
            "check_out": "2026-02-04"  # 3 nights
        }
        response = requests.post(f"{BASE_URL}/api/booking-widget/check-availability", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        rooms = data["available_rooms"]
        
        for room in rooms:
            assert "room_type_id" in room
            assert "name" in room
            assert "base_rate" in room
            assert "total_rate" in room
            assert "nights" in room
            assert "available" in room
            assert "max_occupancy" in room
            
            # Verify nights calculation
            assert room["nights"] == 3
            
            # Verify total_rate = base_rate * nights
            expected_total = room["base_rate"] * room["nights"]
            assert room["total_rate"] == expected_total, f"Expected {expected_total}, got {room['total_rate']}"
            
            print(f"  - {room['name']}: £{room['base_rate']}/night × {room['nights']} nights = £{room['total_rate']}")
        
        print(f"✓ All {len(rooms)} rooms have correct pricing")
    
    def test_availability_missing_fields(self):
        """Test availability check with missing required fields"""
        # Missing check_out
        payload = {
            "property_id": "vilenza-hotel",
            "check_in": "2026-02-01"
        }
        response = requests.post(f"{BASE_URL}/api/booking-widget/check-availability", json=payload)
        assert response.status_code == 400
        print("✓ Missing check_out returns 400")
        
        # Missing property_id
        payload = {
            "check_in": "2026-02-01",
            "check_out": "2026-02-03"
        }
        response = requests.post(f"{BASE_URL}/api/booking-widget/check-availability", json=payload)
        assert response.status_code == 400
        print("✓ Missing property_id returns 400")


class TestBookingWidgetBook:
    """Tests for POST /api/booking-widget/book"""
    
    def test_create_booking_success(self):
        """Test creating a booking successfully"""
        unique_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
        payload = {
            "property_id": "vilenza-hotel",
            "room_type": "Standard Double Room",
            "check_in": "2026-03-01",
            "check_out": "2026-03-03",
            "guest_name": "Test Guest",
            "guest_email": unique_email,
            "guest_phone": "+44 7911 123456",
            "special_requests": "Late check-in please",
            "rate": 100,
            "guests": 2,
            "rooms": 1,
            "currency": "GBP"
        }
        response = requests.post(f"{BASE_URL}/api/booking-widget/book", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "confirmed"
        assert "booking_ref" in data
        assert data["booking_ref"].startswith("WEB-")
        
        booking = data["booking"]
        assert booking["property_id"] == "vilenza-hotel"
        assert booking["room_type"] == "Standard Double Room"
        assert booking["guest_name"] == "Test Guest"
        assert booking["guest_email"] == unique_email
        assert booking["check_in"] == "2026-03-01"
        assert booking["check_out"] == "2026-03-03"
        assert booking["nights"] == 2
        assert booking["total"] == 200  # 100 * 2 nights
        assert booking["status"] == "confirmed"
        assert booking["source"] == "website_widget"
        
        print(f"✓ Booking created: {data['booking_ref']}")
        print(f"  - Guest: {booking['guest_name']}")
        print(f"  - Room: {booking['room_type']}")
        print(f"  - Total: £{booking['total']} for {booking['nights']} nights")
    
    def test_create_booking_missing_required_fields(self):
        """Test booking creation with missing required fields"""
        # Missing guest_name
        payload = {
            "property_id": "vilenza-hotel",
            "room_type": "Standard Double Room",
            "check_in": "2026-03-01",
            "check_out": "2026-03-03",
            "guest_email": "test@example.com"
        }
        response = requests.post(f"{BASE_URL}/api/booking-widget/book", json=payload)
        assert response.status_code == 400
        print("✓ Missing guest_name returns 400")
        
        # Missing guest_email
        payload = {
            "property_id": "vilenza-hotel",
            "room_type": "Standard Double Room",
            "check_in": "2026-03-01",
            "check_out": "2026-03-03",
            "guest_name": "Test Guest"
        }
        response = requests.post(f"{BASE_URL}/api/booking-widget/book", json=payload)
        assert response.status_code == 400
        print("✓ Missing guest_email returns 400")
    
    def test_create_booking_nights_calculation(self):
        """Test that booking correctly calculates nights and total"""
        unique_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
        payload = {
            "property_id": "vilenza-hotel",
            "room_type": "Deluxe King Room",
            "check_in": "2026-04-01",
            "check_out": "2026-04-05",  # 4 nights
            "guest_name": "Test Guest",
            "guest_email": unique_email,
            "rate": 150,
            "guests": 2,
            "rooms": 1,
            "currency": "GBP"
        }
        response = requests.post(f"{BASE_URL}/api/booking-widget/book", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        booking = data["booking"]
        
        assert booking["nights"] == 4
        assert booking["total"] == 600  # 150 * 4 nights
        
        print(f"✓ Booking nights calculation correct: {booking['nights']} nights = £{booking['total']}")
    
    def test_create_booking_with_special_requests(self):
        """Test booking with special requests"""
        unique_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
        special_request = "Early check-in at 10am, extra pillows, quiet room away from elevator"
        
        payload = {
            "property_id": "vilenza-hotel",
            "room_type": "Family Suite",
            "check_in": "2026-05-01",
            "check_out": "2026-05-03",
            "guest_name": "Family Guest",
            "guest_email": unique_email,
            "guest_phone": "+44 7911 999888",
            "special_requests": special_request,
            "rate": 200,
            "guests": 4,
            "rooms": 1,
            "currency": "GBP"
        }
        response = requests.post(f"{BASE_URL}/api/booking-widget/book", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        booking = data["booking"]
        
        assert booking["special_requests"] == special_request
        assert booking["guests"] == 4
        
        print(f"✓ Booking with special requests saved correctly")


class TestBookingWidgetIntegration:
    """Integration tests for the full booking flow"""
    
    def test_full_booking_flow(self):
        """Test complete flow: info -> availability -> book"""
        # Step 1: Get hotel info
        info_response = requests.get(f"{BASE_URL}/api/booking-widget/info/vilenza-hotel")
        assert info_response.status_code == 200
        hotel_info = info_response.json()
        print(f"Step 1: Got hotel info for {hotel_info['hotel_name']}")
        
        # Step 2: Check availability
        avail_payload = {
            "property_id": "vilenza-hotel",
            "check_in": "2026-06-01",
            "check_out": "2026-06-03"
        }
        avail_response = requests.post(f"{BASE_URL}/api/booking-widget/check-availability", json=avail_payload)
        assert avail_response.status_code == 200
        avail_data = avail_response.json()
        
        available_rooms = avail_data["available_rooms"]
        assert len(available_rooms) > 0
        
        selected_room = available_rooms[0]
        print(f"Step 2: Found {len(available_rooms)} available rooms, selected: {selected_room['name']}")
        
        # Step 3: Create booking
        unique_email = f"integration_{uuid.uuid4().hex[:8]}@example.com"
        book_payload = {
            "property_id": "vilenza-hotel",
            "room_type": selected_room["name"],
            "check_in": "2026-06-01",
            "check_out": "2026-06-03",
            "guest_name": "Integration Test Guest",
            "guest_email": unique_email,
            "rate": selected_room["base_rate"],
            "guests": 2,
            "rooms": 1,
            "currency": hotel_info["currency"]
        }
        book_response = requests.post(f"{BASE_URL}/api/booking-widget/book", json=book_payload)
        assert book_response.status_code == 200
        
        booking_data = book_response.json()
        assert booking_data["status"] == "confirmed"
        
        print(f"Step 3: Booking confirmed with ref: {booking_data['booking_ref']}")
        print(f"✓ Full booking flow completed successfully!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
