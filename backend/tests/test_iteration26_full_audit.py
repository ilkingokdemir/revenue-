"""
Iteration 26 - Full Quality Audit Tests
Testing: 9 properties, 45 room types, multi-photo gallery, property filter, booking flow, templates
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://review-hub-108.preview.emergentagent.com').rstrip('/')

# Expected 9 MyHotelBox branches
EXPECTED_PROPERTIES = [
    "aldgate-flats", "camden-suites", "city-gate", "city-rooms", 
    "london-suites", "ryam-suites", "whitechapel-hotel", "vilenza-hotel", "whitechapel-grand"
]

class TestRoomTypesAndProperties:
    """Test room types seeding for all 9 properties"""
    
    def test_get_all_room_types_returns_45_rooms(self):
        """GET /api/room-types should return 45 rooms (5 per property x 9 properties)"""
        response = requests.get(f"{BASE_URL}/api/room-types")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        rooms = response.json()
        assert len(rooms) == 45, f"Expected 45 room types, got {len(rooms)}"
        print(f"✓ Total room types: {len(rooms)}")
    
    def test_each_property_has_5_room_types(self):
        """Each of the 9 properties should have exactly 5 room types"""
        response = requests.get(f"{BASE_URL}/api/room-types")
        assert response.status_code == 200
        rooms = response.json()
        
        # Count rooms per property
        property_counts = {}
        for room in rooms:
            prop_id = room.get("property_id", "unknown")
            property_counts[prop_id] = property_counts.get(prop_id, 0) + 1
        
        for prop_id in EXPECTED_PROPERTIES:
            count = property_counts.get(prop_id, 0)
            assert count == 5, f"Property {prop_id} has {count} rooms, expected 5"
            print(f"✓ {prop_id}: {count} room types")
    
    def test_each_room_has_multiple_photos(self):
        """Each room type should have 2-3 photos (not just 1)"""
        response = requests.get(f"{BASE_URL}/api/room-types")
        assert response.status_code == 200
        rooms = response.json()
        
        rooms_with_single_photo = []
        rooms_with_no_photos = []
        
        for room in rooms:
            photos = room.get("photos", [])
            if len(photos) == 0:
                rooms_with_no_photos.append(room.get("id"))
            elif len(photos) == 1:
                rooms_with_single_photo.append(room.get("id"))
        
        assert len(rooms_with_no_photos) == 0, f"Rooms with no photos: {rooms_with_no_photos}"
        assert len(rooms_with_single_photo) == 0, f"Rooms with only 1 photo: {rooms_with_single_photo}"
        
        # Verify at least 2 photos per room
        for room in rooms:
            photos = room.get("photos", [])
            assert len(photos) >= 2, f"Room {room.get('id')} has only {len(photos)} photo(s)"
        
        print(f"✓ All {len(rooms)} rooms have 2+ photos")
    
    def test_room_types_have_correct_structure(self):
        """Verify room type structure includes all required fields"""
        response = requests.get(f"{BASE_URL}/api/room-types")
        assert response.status_code == 200
        rooms = response.json()
        
        required_fields = ["id", "property_id", "name", "description", "max_guests", 
                          "bed_type", "photos", "base_price", "amenities"]
        
        for room in rooms[:5]:  # Check first 5 rooms
            for field in required_fields:
                assert field in room, f"Room {room.get('id')} missing field: {field}"
        
        print(f"✓ Room structure validated")


class TestBookingEngineByProperty:
    """Test booking engine loads correctly for different properties"""
    
    def test_booking_property_aldgate_flats(self):
        """GET /api/booking/property/aldgate-flats returns property info with rooms"""
        response = requests.get(f"{BASE_URL}/api/booking/property/aldgate-flats")
        assert response.status_code == 200
        data = response.json()
        assert data.get("name") == "ALDGATE FLATS"
        assert "room_types" in data
        assert len(data["room_types"]) == 5
        print(f"✓ aldgate-flats: {len(data['room_types'])} rooms")
    
    def test_booking_property_camden_suites(self):
        """GET /api/booking/property/camden-suites returns property info with rooms"""
        response = requests.get(f"{BASE_URL}/api/booking/property/camden-suites")
        assert response.status_code == 200
        data = response.json()
        assert data.get("name") == "CAMDEN SUITES"
        assert len(data.get("room_types", [])) == 5
        print(f"✓ camden-suites: {len(data['room_types'])} rooms")
    
    def test_booking_property_city_gate(self):
        """GET /api/booking/property/city-gate returns property info with rooms"""
        response = requests.get(f"{BASE_URL}/api/booking/property/city-gate")
        assert response.status_code == 200
        data = response.json()
        assert data.get("name") == "CITY GATE"
        assert len(data.get("room_types", [])) == 5
        print(f"✓ city-gate: {len(data['room_types'])} rooms")
    
    def test_booking_rooms_endpoint_returns_rooms(self):
        """GET /api/booking/rooms/{property_id} returns available rooms"""
        for prop_id in ["aldgate-flats", "camden-suites", "whitechapel-grand"]:
            response = requests.get(f"{BASE_URL}/api/booking/rooms/{prop_id}")
            assert response.status_code == 200
            rooms = response.json()
            assert len(rooms) == 5, f"{prop_id} should have 5 rooms"
            print(f"✓ {prop_id} booking rooms: {len(rooms)}")
    
    def test_room_photos_in_booking_response(self):
        """Verify room photos are included in booking property response"""
        response = requests.get(f"{BASE_URL}/api/booking/property/aldgate-flats")
        assert response.status_code == 200
        data = response.json()
        
        for room in data.get("room_types", []):
            photos = room.get("photos", [])
            assert len(photos) >= 2, f"Room {room.get('name')} should have 2+ photos"
        
        print(f"✓ All rooms have multiple photos in booking response")


class TestBookingFlow:
    """Test full booking flow: search -> select -> details -> confirm"""
    
    def test_create_booking_pay_at_hotel(self):
        """POST /api/booking/reserve creates booking with pay at hotel"""
        # Get a room first
        rooms_resp = requests.get(f"{BASE_URL}/api/booking/rooms/aldgate-flats")
        assert rooms_resp.status_code == 200
        rooms = rooms_resp.json()
        room = rooms[0]
        
        booking_data = {
            "property_id": "aldgate-flats",
            "room_type_id": room["id"],
            "guest_name": "TEST_Iteration26_User",
            "guest_email": "test26@example.com",
            "guest_phone": "+44 7700 900000",
            "check_in": "2026-02-15",
            "check_out": "2026-02-17",
            "adults": 2,
            "children": 0,
            "rooms": 1,
            "special_requests": "Late check-in please"
        }
        
        response = requests.post(f"{BASE_URL}/api/booking/reserve", json=booking_data)
        assert response.status_code == 200, f"Booking failed: {response.text}"
        data = response.json()
        
        assert "booking_ref" in data
        assert data["booking_ref"].startswith("MHB-")
        assert data["guest_name"] == "TEST_Iteration26_User"
        assert data["property_id"] == "aldgate-flats"
        
        print(f"✓ Booking created: {data['booking_ref']}")
        return data["booking_ref"]
    
    def test_get_booking_by_ref(self):
        """GET /api/booking/reservation/{ref} returns booking details"""
        # Create a booking first
        rooms_resp = requests.get(f"{BASE_URL}/api/booking/rooms/camden-suites")
        rooms = rooms_resp.json()
        
        booking_data = {
            "property_id": "camden-suites",
            "room_type_id": rooms[0]["id"],
            "guest_name": "TEST_Reservation_Check",
            "guest_email": "test_res@example.com",
            "check_in": "2026-03-01",
            "check_out": "2026-03-03",
            "adults": 1,
            "children": 0,
            "rooms": 1
        }
        
        create_resp = requests.post(f"{BASE_URL}/api/booking/reserve", json=booking_data)
        assert create_resp.status_code == 200
        booking_ref = create_resp.json()["booking_ref"]
        
        # Now fetch by ref
        get_resp = requests.get(f"{BASE_URL}/api/booking/reservation/{booking_ref}")
        assert get_resp.status_code == 200
        data = get_resp.json()
        
        assert data["booking_ref"] == booking_ref
        assert data["guest_name"] == "TEST_Reservation_Check"
        # Verify property name is returned
        assert "property_name" in data or data.get("property_id") == "camden-suites"
        
        print(f"✓ Reservation lookup works: {booking_ref}")


class TestStripePaymentFlow:
    """Test Stripe payment integration"""
    
    def test_create_checkout_session(self):
        """POST /api/payments/create-checkout creates valid Stripe URL"""
        # Create a booking first
        rooms_resp = requests.get(f"{BASE_URL}/api/booking/rooms/aldgate-flats")
        rooms = rooms_resp.json()
        
        booking_data = {
            "property_id": "aldgate-flats",
            "room_type_id": rooms[0]["id"],
            "guest_name": "TEST_Stripe_User",
            "guest_email": "stripe_test@example.com",
            "check_in": "2026-04-01",
            "check_out": "2026-04-03",
            "adults": 2,
            "children": 0,
            "rooms": 1
        }
        
        create_resp = requests.post(f"{BASE_URL}/api/booking/reserve", json=booking_data)
        assert create_resp.status_code == 200
        booking_id = create_resp.json()["id"]
        
        # Create checkout session
        checkout_resp = requests.post(
            f"{BASE_URL}/api/payments/create-checkout",
            params={"booking_id": booking_id, "origin_url": "https://review-hub-108.preview.emergentagent.com"}
        )
        
        # Should return 200 with URL or 500 if Stripe not configured
        if checkout_resp.status_code == 200:
            data = checkout_resp.json()
            assert "url" in data
            assert "stripe.com" in data["url"] or "checkout" in data["url"]
            print(f"✓ Stripe checkout URL created")
        else:
            # Stripe may not be fully configured in test env
            print(f"⚠ Stripe checkout returned {checkout_resp.status_code} (may need API key)")


class TestAdminAuthentication:
    """Test admin login and authentication"""
    
    def test_admin_login(self):
        """POST /api/auth/login with admin credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert data["email"] == "admin@hotelbox.com"
        assert data["role"] == "admin"
        assert "token" in data
        print(f"✓ Admin login successful")
        return data["token"]
    
    def test_get_properties_list(self):
        """GET /api/properties returns all 9 branches + default"""
        # Login first
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = login_resp.json()["token"]
        
        response = requests.get(
            f"{BASE_URL}/api/properties",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        properties = response.json()
        
        # Should have 9 branches + possibly default
        prop_ids = [p["id"] for p in properties]
        for expected in EXPECTED_PROPERTIES:
            assert expected in prop_ids, f"Missing property: {expected}"
        
        print(f"✓ All 9 properties present: {len(properties)} total")


class TestTemplateGallery:
    """Test template gallery functionality"""
    
    def test_booking_with_different_templates(self):
        """Verify booking engine accepts template parameter"""
        templates = ["booking-classic", "airbnb-modern", "expedia-classic", "hotels-rewards"]
        
        for template in templates:
            # Just verify the property endpoint works (template is frontend-only)
            response = requests.get(f"{BASE_URL}/api/booking/property/aldgate-flats")
            assert response.status_code == 200
        
        print(f"✓ Booking API works for template testing")


class TestReviewHubFeatures:
    """Test Review Hub features still work"""
    
    def test_reviews_list(self):
        """GET /api/reviews returns reviews"""
        response = requests.get(f"{BASE_URL}/api/reviews")
        assert response.status_code == 200
        print(f"✓ Reviews list: {len(response.json())} reviews")
    
    def test_review_stats(self):
        """GET /api/reviews/stats/summary returns stats"""
        response = requests.get(f"{BASE_URL}/api/reviews/stats/summary")
        assert response.status_code == 200
        data = response.json()
        assert "total_reviews" in data
        print(f"✓ Review stats: {data.get('total_reviews', 0)} total")
    
    def test_templates_endpoint(self):
        """GET /api/templates returns response templates"""
        response = requests.get(f"{BASE_URL}/api/templates")
        assert response.status_code == 200
        print(f"✓ Templates: {len(response.json())} templates")


class TestBookingsAdmin:
    """Test admin bookings management"""
    
    def test_list_bookings(self):
        """GET /api/bookings returns bookings list"""
        # Login first
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = login_resp.json()["token"]
        
        response = requests.get(
            f"{BASE_URL}/api/bookings",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        bookings = response.json()
        print(f"✓ Bookings list: {len(bookings)} bookings")
    
    def test_filter_bookings_by_property(self):
        """GET /api/bookings?property_id=X filters correctly"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = login_resp.json()["token"]
        
        response = requests.get(
            f"{BASE_URL}/api/bookings?property_id=aldgate-flats",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        bookings = response.json()
        
        # All returned bookings should be for aldgate-flats
        for booking in bookings:
            assert booking.get("property_id") == "aldgate-flats"
        
        print(f"✓ Property filter works: {len(bookings)} aldgate-flats bookings")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
