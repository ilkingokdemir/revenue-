"""
Iteration 93 - Booking Engine Admin Panel API Tests
Tests for:
- Room Photos tab: room-photo and room-gallery upload endpoints
- Guest Reviews tab: CRUD operations (list, create, delete)
- Theme & Branding tab: config get/put endpoints
- Public booking-widget/info endpoint returns theme config
"""
import pytest
import requests
import os
import io

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://review-hub-108.preview.emergentagent.com"

ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
PROPERTY_ID = "all"  # Default property ID used in admin panel


class TestBookingEngineAdminAPIs:
    """Test Booking Engine Admin Panel APIs"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for admin user"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.cookies
    
    @pytest.fixture(scope="class")
    def session(self, auth_token):
        """Create authenticated session"""
        s = requests.Session()
        s.cookies.update(auth_token)
        return s

    # ==================== PUBLIC: WIDGET INFO ====================
    
    def test_widget_info_returns_theme(self):
        """GET /api/booking-widget/info/{property_id} returns theme config"""
        response = requests.get(f"{BASE_URL}/api/booking-widget/info/{PROPERTY_ID}")
        assert response.status_code == 200, f"Widget info failed: {response.text}"
        data = response.json()
        
        # Verify theme fields exist
        assert "theme" in data, "Response should contain theme"
        theme = data["theme"]
        assert "accent_color" in theme, "Theme should have accent_color"
        assert "hero_image" in theme, "Theme should have hero_image"
        assert "tagline" in theme, "Theme should have tagline"
        assert "subtitle" in theme, "Theme should have subtitle"
        
        # Verify rooms array exists
        assert "rooms" in data, "Response should contain rooms"
        assert isinstance(data["rooms"], list), "Rooms should be a list"
        print(f"Widget info returned {len(data['rooms'])} rooms with theme config")
    
    def test_widget_info_returns_reviews(self):
        """GET /api/booking-widget/info/{property_id} returns reviews"""
        response = requests.get(f"{BASE_URL}/api/booking-widget/info/{PROPERTY_ID}")
        assert response.status_code == 200
        data = response.json()
        
        assert "reviews" in data, "Response should contain reviews"
        assert "avg_rating" in data, "Response should contain avg_rating"
        assert "review_count" in data, "Response should contain review_count"
        print(f"Widget info returned {data['review_count']} reviews with avg rating {data['avg_rating']}")

    # ==================== ADMIN: WIDGET CONFIG ====================
    
    def test_widget_config_requires_auth(self):
        """GET /api/booking-widget/config/{property_id} requires authentication"""
        response = requests.get(f"{BASE_URL}/api/booking-widget/config/{PROPERTY_ID}")
        assert response.status_code == 401, "Should require authentication"
        print("Widget config GET correctly requires auth")
    
    def test_widget_config_get(self, session):
        """GET /api/booking-widget/config/{property_id} returns config with auth"""
        response = session.get(f"{BASE_URL}/api/booking-widget/config/{PROPERTY_ID}")
        assert response.status_code == 200, f"Config get failed: {response.text}"
        data = response.json()
        
        assert "property_id" in data, "Config should have property_id"
        print(f"Widget config retrieved: {data}")
    
    def test_widget_config_update(self, session):
        """PUT /api/booking-widget/config/{property_id} updates theme config"""
        test_config = {
            "accent_color": "#2a5f8f",
            "hero_image": "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=1920&q=80",
            "tagline": "Test Tagline for Iteration 93",
            "subtitle": "Test subtitle for booking engine admin panel"
        }
        
        response = session.put(f"{BASE_URL}/api/booking-widget/config/{PROPERTY_ID}", json=test_config)
        assert response.status_code == 200, f"Config update failed: {response.text}"
        data = response.json()
        assert data.get("status") == "saved", "Should return saved status"
        
        # Verify the update persisted by checking public info endpoint
        info_response = requests.get(f"{BASE_URL}/api/booking-widget/info/{PROPERTY_ID}")
        assert info_response.status_code == 200
        info_data = info_response.json()
        theme = info_data.get("theme", {})
        
        assert theme.get("accent_color") == test_config["accent_color"], "Accent color should be updated"
        assert theme.get("tagline") == test_config["tagline"], "Tagline should be updated"
        print(f"Widget config updated and verified: accent_color={theme.get('accent_color')}, tagline={theme.get('tagline')}")
    
    def test_widget_config_update_requires_auth(self):
        """PUT /api/booking-widget/config/{property_id} requires authentication"""
        response = requests.put(f"{BASE_URL}/api/booking-widget/config/{PROPERTY_ID}", json={
            "accent_color": "#ff0000"
        })
        assert response.status_code == 401, "Should require authentication"
        print("Widget config PUT correctly requires auth")

    # ==================== ADMIN: GUEST REVIEWS CRUD ====================
    
    def test_reviews_list_requires_auth(self):
        """GET /api/booking-widget/reviews/{property_id} requires authentication"""
        response = requests.get(f"{BASE_URL}/api/booking-widget/reviews/{PROPERTY_ID}")
        assert response.status_code == 401, "Should require authentication"
        print("Reviews list correctly requires auth")
    
    def test_reviews_list(self, session):
        """GET /api/booking-widget/reviews/{property_id} returns reviews list"""
        response = session.get(f"{BASE_URL}/api/booking-widget/reviews/{PROPERTY_ID}")
        assert response.status_code == 200, f"Reviews list failed: {response.text}"
        data = response.json()
        
        assert isinstance(data, list), "Should return a list"
        print(f"Reviews list returned {len(data)} reviews")
    
    def test_reviews_create_requires_auth(self):
        """POST /api/booking-widget/reviews requires authentication"""
        response = requests.post(f"{BASE_URL}/api/booking-widget/reviews", json={
            "property_id": PROPERTY_ID,
            "guest_name": "Test Guest",
            "rating": 9.0
        })
        assert response.status_code == 401, "Should require authentication"
        print("Reviews create correctly requires auth")
    
    def test_reviews_create_and_delete(self, session):
        """POST /api/booking-widget/reviews creates review, DELETE removes it"""
        # Create a test review
        test_review = {
            "property_id": PROPERTY_ID,
            "guest_name": "TEST_Iter93_Guest",
            "country": "Test Country",
            "rating": 9.5,
            "title": "Test Review Title",
            "comment": "This is a test review for iteration 93 testing",
            "date": "April 2026"
        }
        
        create_response = session.post(f"{BASE_URL}/api/booking-widget/reviews", json=test_review)
        assert create_response.status_code == 200, f"Review create failed: {create_response.text}"
        created = create_response.json()
        
        assert "id" in created, "Created review should have id"
        assert created.get("guest_name") == test_review["guest_name"], "Guest name should match"
        assert created.get("rating") == test_review["rating"], "Rating should match"
        assert created.get("title") == test_review["title"], "Title should match"
        review_id = created["id"]
        print(f"Review created with id: {review_id}")
        
        # Verify it appears in the list
        list_response = session.get(f"{BASE_URL}/api/booking-widget/reviews/{PROPERTY_ID}")
        assert list_response.status_code == 200
        reviews = list_response.json()
        found = any(r.get("id") == review_id for r in reviews)
        assert found, "Created review should appear in list"
        print("Created review found in list")
        
        # Delete the review
        delete_response = session.delete(f"{BASE_URL}/api/booking-widget/reviews/{review_id}")
        assert delete_response.status_code == 200, f"Review delete failed: {delete_response.text}"
        delete_data = delete_response.json()
        assert delete_data.get("status") == "deleted", "Should return deleted status"
        print(f"Review {review_id} deleted")
        
        # Verify it's removed from the list
        list_response2 = session.get(f"{BASE_URL}/api/booking-widget/reviews/{PROPERTY_ID}")
        reviews2 = list_response2.json()
        found2 = any(r.get("id") == review_id for r in reviews2)
        assert not found2, "Deleted review should not appear in list"
        print("Deleted review no longer in list - CRUD cycle complete")
    
    def test_reviews_delete_requires_auth(self):
        """DELETE /api/booking-widget/reviews/{review_id} requires authentication"""
        response = requests.delete(f"{BASE_URL}/api/booking-widget/reviews/fake-id")
        assert response.status_code == 401, "Should require authentication"
        print("Reviews delete correctly requires auth")

    # ==================== ADMIN: ROOM PHOTO UPLOAD ====================
    
    def test_room_photo_upload_requires_auth(self):
        """POST /api/booking-widget/room-photo/{room_id} requires authentication"""
        # Create a simple test image
        files = {"file": ("test.jpg", b"fake image content", "image/jpeg")}
        response = requests.post(f"{BASE_URL}/api/booking-widget/room-photo/standard", files=files)
        assert response.status_code == 401, "Should require authentication"
        print("Room photo upload correctly requires auth")
    
    def test_room_photo_upload(self, session):
        """POST /api/booking-widget/room-photo/{room_id} uploads main photo"""
        # Create a minimal valid JPEG (1x1 pixel)
        # This is a minimal valid JPEG file
        jpeg_bytes = bytes([
            0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
            0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
            0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09,
            0x09, 0x08, 0x0A, 0x0C, 0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
            0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D, 0x1A, 0x1C, 0x1C, 0x20,
            0x24, 0x2E, 0x27, 0x20, 0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29,
            0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27, 0x39, 0x3D, 0x38, 0x32,
            0x3C, 0x2E, 0x33, 0x34, 0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01,
            0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4, 0x00, 0x1F, 0x00, 0x00,
            0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
            0x09, 0x0A, 0x0B, 0xFF, 0xC4, 0x00, 0xB5, 0x10, 0x00, 0x02, 0x01, 0x03,
            0x03, 0x02, 0x04, 0x03, 0x05, 0x05, 0x04, 0x04, 0x00, 0x00, 0x01, 0x7D,
            0x01, 0x02, 0x03, 0x00, 0x04, 0x11, 0x05, 0x12, 0x21, 0x31, 0x41, 0x06,
            0x13, 0x51, 0x61, 0x07, 0x22, 0x71, 0x14, 0x32, 0x81, 0x91, 0xA1, 0x08,
            0x23, 0x42, 0xB1, 0xC1, 0x15, 0x52, 0xD1, 0xF0, 0x24, 0x33, 0x62, 0x72,
            0x82, 0x09, 0x0A, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x25, 0x26, 0x27, 0x28,
            0x29, 0x2A, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3A, 0x43, 0x44, 0x45,
            0x46, 0x47, 0x48, 0x49, 0x4A, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59,
            0x5A, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6A, 0x73, 0x74, 0x75,
            0x76, 0x77, 0x78, 0x79, 0x7A, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89,
            0x8A, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9A, 0xA2, 0xA3,
            0xA4, 0xA5, 0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6,
            0xB7, 0xB8, 0xB9, 0xBA, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8, 0xC9,
            0xCA, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xD9, 0xDA, 0xE1, 0xE2,
            0xE3, 0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA, 0xF1, 0xF2, 0xF3, 0xF4,
            0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFF, 0xDA, 0x00, 0x08, 0x01, 0x01,
            0x00, 0x00, 0x3F, 0x00, 0xFB, 0xD5, 0xDB, 0x20, 0xA8, 0xF1, 0x7E, 0xA8,
            0xA2, 0x80, 0x0A, 0x28, 0xA0, 0x02, 0x80, 0xFF, 0xD9
        ])
        
        files = {"file": ("test_iter93.jpg", jpeg_bytes, "image/jpeg")}
        response = session.post(f"{BASE_URL}/api/booking-widget/room-photo/standard", files=files)
        assert response.status_code == 200, f"Room photo upload failed: {response.text}"
        data = response.json()
        
        assert data.get("status") == "uploaded", "Should return uploaded status"
        assert "url" in data, "Should return photo URL"
        assert data["url"].startswith("/api/uploads/rooms/"), "URL should be in uploads/rooms path"
        print(f"Room photo uploaded: {data['url']}")
    
    def test_room_gallery_upload_requires_auth(self):
        """POST /api/booking-widget/room-gallery/{room_id} requires authentication"""
        files = {"file": ("test.jpg", b"fake image content", "image/jpeg")}
        response = requests.post(f"{BASE_URL}/api/booking-widget/room-gallery/standard", files=files)
        assert response.status_code == 401, "Should require authentication"
        print("Room gallery upload correctly requires auth")
    
    def test_room_gallery_upload(self, session):
        """POST /api/booking-widget/room-gallery/{room_id} uploads gallery photo"""
        # Create a minimal valid JPEG
        jpeg_bytes = bytes([
            0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
            0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
            0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09,
            0x09, 0x08, 0x0A, 0x0C, 0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
            0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D, 0x1A, 0x1C, 0x1C, 0x20,
            0x24, 0x2E, 0x27, 0x20, 0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29,
            0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27, 0x39, 0x3D, 0x38, 0x32,
            0x3C, 0x2E, 0x33, 0x34, 0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01,
            0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4, 0x00, 0x1F, 0x00, 0x00,
            0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
            0x09, 0x0A, 0x0B, 0xFF, 0xDA, 0x00, 0x08, 0x01, 0x01, 0x00, 0x00, 0x3F,
            0x00, 0x7F, 0xFF, 0xD9
        ])
        
        files = {"file": ("test_gallery_iter93.jpg", jpeg_bytes, "image/jpeg")}
        response = session.post(f"{BASE_URL}/api/booking-widget/room-gallery/standard", files=files)
        assert response.status_code == 200, f"Room gallery upload failed: {response.text}"
        data = response.json()
        
        assert data.get("status") == "uploaded", "Should return uploaded status"
        assert "url" in data, "Should return photo URL"
        print(f"Room gallery photo uploaded: {data['url']}")

    # ==================== PUBLIC: GALLERY API ====================
    
    def test_public_gallery_api(self):
        """GET /api/booking-widget/gallery/{property_id} returns gallery images"""
        response = requests.get(f"{BASE_URL}/api/booking-widget/gallery/{PROPERTY_ID}")
        assert response.status_code == 200, f"Gallery API failed: {response.text}"
        data = response.json()
        
        assert isinstance(data, list), "Should return a list"
        assert len(data) > 0, "Should have at least one image"
        
        # Check structure of first image
        first = data[0]
        assert "url" in first, "Image should have url"
        assert "caption" in first, "Image should have caption"
        assert "type" in first, "Image should have type"
        assert first["type"] in ["room", "property"], "Type should be room or property"
        print(f"Gallery API returned {len(data)} images")


class TestBookingEnginePublicAPIs:
    """Test public booking widget APIs"""
    
    def test_check_availability(self):
        """POST /api/booking-widget/check-availability returns available rooms"""
        response = requests.post(f"{BASE_URL}/api/booking-widget/check-availability", json={
            "property_id": PROPERTY_ID,
            "check_in": "2026-05-01",
            "check_out": "2026-05-03"
        })
        assert response.status_code == 200, f"Check availability failed: {response.text}"
        data = response.json()
        
        assert "available_rooms" in data, "Should have available_rooms"
        assert "check_in" in data, "Should have check_in"
        assert "check_out" in data, "Should have check_out"
        
        rooms = data["available_rooms"]
        assert isinstance(rooms, list), "available_rooms should be a list"
        if len(rooms) > 0:
            room = rooms[0]
            assert "room_type_id" in room, "Room should have room_type_id"
            assert "name" in room, "Room should have name"
            assert "base_rate" in room, "Room should have base_rate"
            assert "total_rate" in room, "Room should have total_rate"
            assert "nights" in room, "Room should have nights"
        print(f"Check availability returned {len(rooms)} available rooms")
    
    def test_create_booking(self):
        """POST /api/booking-widget/book creates a booking"""
        booking_data = {
            "property_id": PROPERTY_ID,
            "room_type": "Standard Room",
            "check_in": "2026-06-01",
            "check_out": "2026-06-03",
            "guest_name": "TEST_Iter93_Booking",
            "guest_email": "test_iter93@example.com",
            "guest_phone": "+1234567890",
            "rate": 100,
            "rooms": 1,
            "guests": 2,
            "special_requests": "Test booking for iteration 93"
        }
        
        response = requests.post(f"{BASE_URL}/api/booking-widget/book", json=booking_data)
        assert response.status_code == 200, f"Create booking failed: {response.text}"
        data = response.json()
        
        assert data.get("status") == "confirmed", "Booking should be confirmed"
        assert "booking_ref" in data, "Should have booking_ref"
        assert data["booking_ref"].startswith("WEB-"), "Booking ref should start with WEB-"
        assert "booking" in data, "Should have booking details"
        
        booking = data["booking"]
        assert booking.get("guest_name") == booking_data["guest_name"], "Guest name should match"
        assert booking.get("guest_email") == booking_data["guest_email"], "Guest email should match"
        assert booking.get("nights") == 2, "Should be 2 nights"
        assert booking.get("total") == 200, "Total should be 200 (100 * 2 nights)"
        print(f"Booking created: {data['booking_ref']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
