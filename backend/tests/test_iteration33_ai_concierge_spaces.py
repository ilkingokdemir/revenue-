"""
Iteration 33 - AI Concierge Chat & Space/Hourly Bookings Tests
Tests for:
- AI Concierge Chat (GPT-5.2 powered Q&A chatbot)
- Hourly/Space Bookings (meeting rooms, parking, event halls)
- Spaces API (list, book)
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestSpacesAPI:
    """Tests for Spaces/Hourly Booking API"""
    
    def test_get_spaces_for_property(self):
        """GET /api/spaces/{property_id} - should return 8 seeded spaces"""
        response = requests.get(f"{BASE_URL}/api/spaces/aldgate-flats")
        assert response.status_code == 200
        
        spaces = response.json()
        assert isinstance(spaces, list)
        assert len(spaces) == 8, f"Expected 8 spaces, got {len(spaces)}"
        
        # Verify space structure
        space = spaces[0]
        assert "id" in space
        assert "name" in space
        assert "category" in space
        assert "hourly_rate" in space
        assert "capacity" in space
        assert "is_active" in space
        
        # Verify expected space names
        space_names = [s["name"] for s in spaces]
        expected_names = ["Meeting Room", "Conference Room", "Boardroom", "Co-working Desk", 
                         "Private Office", "Event Hall", "Parking Space", "Spa Treatment Room"]
        for name in expected_names:
            assert name in space_names, f"Missing space: {name}"
    
    def test_get_spaces_nonexistent_property(self):
        """GET /api/spaces/{property_id} - should return empty list for nonexistent property"""
        response = requests.get(f"{BASE_URL}/api/spaces/nonexistent-property-xyz")
        assert response.status_code == 200
        assert response.json() == []
    
    def test_book_space_success(self):
        """POST /api/spaces/book - should create booking with correct hour calculation"""
        # First get a space ID
        spaces_response = requests.get(f"{BASE_URL}/api/spaces/aldgate-flats")
        spaces = spaces_response.json()
        meeting_room = next((s for s in spaces if s["name"] == "Meeting Room"), spaces[0])
        
        # Book for 3 hours (09:00 - 12:00)
        params = {
            "property_id": "aldgate-flats",
            "space_id": meeting_room["id"],
            "guest_name": "TEST_Space_Booking_User",
            "guest_email": "test_space@example.com",
            "booking_date": "2026-04-20",
            "start_time": "09:00",
            "end_time": "12:00",
            "guest_phone": "+44123456789",
            "notes": "Test booking"
        }
        
        response = requests.post(f"{BASE_URL}/api/spaces/book", params=params)
        assert response.status_code == 200
        
        booking = response.json()
        assert booking["space_name"] == meeting_room["name"]
        assert booking["guest_name"] == "TEST_Space_Booking_User"
        assert booking["guest_email"] == "test_space@example.com"
        assert booking["booking_date"] == "2026-04-20"
        assert booking["start_time"] == "09:00"
        assert booking["end_time"] == "12:00"
        assert booking["hours"] == 3.0
        # Meeting Room is £25/hr, so 3 hours = £75
        assert booking["total_price"] == 75.0
        assert booking["status"] == "confirmed"
        assert "id" in booking
    
    def test_book_space_invalid_time(self):
        """POST /api/spaces/book - should reject if end time before start time"""
        spaces_response = requests.get(f"{BASE_URL}/api/spaces/aldgate-flats")
        spaces = spaces_response.json()
        space = spaces[0]
        
        params = {
            "property_id": "aldgate-flats",
            "space_id": space["id"],
            "guest_name": "TEST_Invalid_Time",
            "guest_email": "test@example.com",
            "booking_date": "2026-04-20",
            "start_time": "14:00",
            "end_time": "10:00"  # End before start
        }
        
        response = requests.post(f"{BASE_URL}/api/spaces/book", params=params)
        assert response.status_code == 400
        assert "End time must be after start time" in response.json()["detail"]
    
    def test_book_space_not_found(self):
        """POST /api/spaces/book - should return 404 for nonexistent space"""
        params = {
            "property_id": "aldgate-flats",
            "space_id": "nonexistent-space-id",
            "guest_name": "TEST_User",
            "guest_email": "test@example.com",
            "booking_date": "2026-04-20",
            "start_time": "09:00",
            "end_time": "10:00"
        }
        
        response = requests.post(f"{BASE_URL}/api/spaces/book", params=params)
        assert response.status_code == 404
        assert "Space not found" in response.json()["detail"]
    
    def test_book_conference_room_pricing(self):
        """POST /api/spaces/book - verify Conference Room pricing (£50/hr)"""
        spaces_response = requests.get(f"{BASE_URL}/api/spaces/aldgate-flats")
        spaces = spaces_response.json()
        conf_room = next((s for s in spaces if s["name"] == "Conference Room"), None)
        assert conf_room is not None, "Conference Room not found"
        
        # Book for 2 hours
        params = {
            "property_id": "aldgate-flats",
            "space_id": conf_room["id"],
            "guest_name": "TEST_Conf_Room_User",
            "guest_email": "conf@example.com",
            "booking_date": "2026-04-21",
            "start_time": "10:00",
            "end_time": "12:00"
        }
        
        response = requests.post(f"{BASE_URL}/api/spaces/book", params=params)
        assert response.status_code == 200
        
        booking = response.json()
        assert booking["hours"] == 2.0
        # Conference Room is £50/hr, so 2 hours = £100
        assert booking["total_price"] == 100.0


class TestAIConciergeAPI:
    """Tests for AI Concierge Chat API"""
    
    def test_concierge_chat_basic(self):
        """POST /api/concierge/chat - should return AI reply with session_id"""
        params = {
            "property_id": "aldgate-flats",
            "message": "What are your check-in times?",
            "session_id": ""
        }
        
        response = requests.post(f"{BASE_URL}/api/concierge/chat", params=params)
        assert response.status_code == 200
        
        data = response.json()
        assert "reply" in data
        assert "session_id" in data
        assert len(data["reply"]) > 0
        assert len(data["session_id"]) > 0
        # Reply should mention check-in times
        assert any(word in data["reply"].lower() for word in ["check", "in", "time", "16:00", "15:00", "22:00"])
    
    def test_concierge_chat_session_tracking(self):
        """POST /api/concierge/chat - should maintain session across messages"""
        # First message - get session_id
        params1 = {
            "property_id": "aldgate-flats",
            "message": "What rooms do you have?",
            "session_id": ""
        }
        
        response1 = requests.post(f"{BASE_URL}/api/concierge/chat", params=params1)
        assert response1.status_code == 200
        data1 = response1.json()
        session_id = data1["session_id"]
        assert session_id
        
        # Second message - use same session_id
        params2 = {
            "property_id": "aldgate-flats",
            "message": "What about the Family Suite?",
            "session_id": session_id
        }
        
        response2 = requests.post(f"{BASE_URL}/api/concierge/chat", params=params2)
        assert response2.status_code == 200
        data2 = response2.json()
        # Session ID should be maintained
        assert data2["session_id"] == session_id
        # Reply should be contextual (about Family Suite)
        assert len(data2["reply"]) > 0
    
    def test_concierge_chat_about_spaces(self):
        """POST /api/concierge/chat - should know about meeting rooms/spaces"""
        params = {
            "property_id": "aldgate-flats",
            "message": "Do you have meeting rooms available?",
            "session_id": ""
        }
        
        response = requests.post(f"{BASE_URL}/api/concierge/chat", params=params)
        assert response.status_code == 200
        
        data = response.json()
        assert "reply" in data
        # Should mention meeting rooms or spaces
        reply_lower = data["reply"].lower()
        assert any(word in reply_lower for word in ["meeting", "room", "conference", "space", "hour", "£"])
    
    def test_concierge_chat_about_facilities(self):
        """POST /api/concierge/chat - should answer about facilities"""
        params = {
            "property_id": "aldgate-flats",
            "message": "Is there parking available?",
            "session_id": ""
        }
        
        response = requests.post(f"{BASE_URL}/api/concierge/chat", params=params)
        assert response.status_code == 200
        
        data = response.json()
        assert "reply" in data
        assert len(data["reply"]) > 10  # Should have a meaningful response


class TestExistingBookingEngineFlows:
    """Verify existing booking engine flows still work"""
    
    def test_get_property(self):
        """GET /api/booking/property/{property_id} - should return property data"""
        response = requests.get(f"{BASE_URL}/api/booking/property/aldgate-flats")
        assert response.status_code == 200
        
        data = response.json()
        assert "id" in data
        assert "name" in data
        assert data["id"] == "aldgate-flats"
    
    def test_get_rooms(self):
        """GET /api/booking/rooms/{property_id} - should return available rooms"""
        response = requests.get(f"{BASE_URL}/api/booking/rooms/aldgate-flats?check_in=2026-04-20&check_out=2026-04-22&adults=2&children=0")
        assert response.status_code == 200
        
        rooms = response.json()
        assert isinstance(rooms, list)
        assert len(rooms) > 0
        
        room = rooms[0]
        assert "id" in room
        assert "name" in room
        assert "base_price" in room
    
    def test_get_reviews(self):
        """GET /api/booking/reviews/{property_id} - should return reviews"""
        response = requests.get(f"{BASE_URL}/api/booking/reviews/aldgate-flats?limit=6")
        assert response.status_code == 200
        
        reviews = response.json()
        assert isinstance(reviews, list)


class TestSpaceTemplates:
    """Test space templates endpoint"""
    
    def test_get_space_templates(self):
        """GET /api/spaces/templates - should return space type templates"""
        response = requests.get(f"{BASE_URL}/api/spaces/templates")
        assert response.status_code == 200
        
        templates = response.json()
        assert isinstance(templates, list)
        assert len(templates) >= 8
        
        # Verify template structure
        template = templates[0]
        assert "name" in template
        assert "category" in template
        assert "hourly_rate" in template


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
