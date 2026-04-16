"""
Iteration 92 - Gallery, Lightbox, Admin Reviews CRUD, Room Photo Upload Tests
Tests:
- POST /api/booking-widget/room-photo/{room_id} - Admin room photo upload
- POST /api/booking-widget/room-gallery/{room_id} - Admin gallery photo upload
- GET /api/booking-widget/reviews/{property_id} - Admin list reviews
- POST /api/booking-widget/reviews - Admin create review
- DELETE /api/booking-widget/reviews/{review_id} - Admin delete review
- GET /api/booking-widget/gallery/{property_id} - Public gallery endpoint
"""
import pytest
import requests
import os
import io
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
PROPERTY_ID = "vilenza-hotel"
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


class TestAuth:
    """Authentication for admin endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            data = response.json()
            return data.get("access_token") or data.get("token")
        pytest.skip(f"Auth failed: {response.status_code} - {response.text}")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}"}


class TestPublicGalleryEndpoint(TestAuth):
    """Test GET /api/booking-widget/gallery/{property_id} - Public endpoint"""
    
    def test_gallery_returns_images(self):
        """Gallery endpoint returns array of images"""
        response = requests.get(f"{BASE_URL}/api/booking-widget/gallery/{PROPERTY_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Gallery should return a list"
        assert len(data) >= 1, "Gallery should have at least 1 image"
        print(f"Gallery returned {len(data)} images")
    
    def test_gallery_image_structure(self):
        """Each gallery image has url, caption, type"""
        response = requests.get(f"{BASE_URL}/api/booking-widget/gallery/{PROPERTY_ID}")
        assert response.status_code == 200
        
        data = response.json()
        for i, img in enumerate(data[:3]):  # Check first 3
            assert "url" in img, f"Image {i} missing 'url'"
            assert "caption" in img, f"Image {i} missing 'caption'"
            assert "type" in img, f"Image {i} missing 'type'"
            assert img["type"] in ["room", "property"], f"Image {i} has invalid type: {img['type']}"
            print(f"Image {i}: {img['caption']} ({img['type']})")
    
    def test_gallery_default_images(self):
        """Gallery returns default 6 images when no custom photos"""
        response = requests.get(f"{BASE_URL}/api/booking-widget/gallery/{PROPERTY_ID}")
        assert response.status_code == 200
        
        data = response.json()
        # Should have at least 6 default images
        assert len(data) >= 6, f"Expected at least 6 images, got {len(data)}"
        
        # Check URLs are valid (Unsplash/Pexels)
        for img in data[:6]:
            url = img.get("url", "")
            assert url.startswith("http"), f"Invalid URL: {url}"
            print(f"Gallery image URL: {url[:60]}...")


class TestAdminReviewsCRUD(TestAuth):
    """Test Admin Reviews CRUD endpoints"""
    
    def test_list_reviews_requires_auth(self):
        """GET /api/booking-widget/reviews/{property_id} requires auth"""
        response = requests.get(f"{BASE_URL}/api/booking-widget/reviews/{PROPERTY_ID}")
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
    
    def test_list_reviews_with_auth(self, auth_headers):
        """GET /api/booking-widget/reviews/{property_id} returns reviews list"""
        response = requests.get(
            f"{BASE_URL}/api/booking-widget/reviews/{PROPERTY_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Should return a list"
        print(f"Found {len(data)} reviews for property")
        
        if len(data) > 0:
            review = data[0]
            print(f"First review: {review.get('guest_name')} - {review.get('rating')}")
    
    def test_create_review_requires_auth(self):
        """POST /api/booking-widget/reviews requires auth"""
        response = requests.post(f"{BASE_URL}/api/booking-widget/reviews", json={
            "property_id": PROPERTY_ID,
            "guest_name": "Test Guest",
            "rating": 9.0
        })
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
    
    def test_create_review_with_auth(self, auth_headers):
        """POST /api/booking-widget/reviews creates a new review"""
        test_review = {
            "property_id": PROPERTY_ID,
            "guest_name": f"TEST_Iter92_{uuid.uuid4().hex[:6]}",
            "country": "Test Country",
            "rating": 9.5,
            "title": "Test Review Title",
            "comment": "This is a test review created by iteration 92 testing",
            "date": "January 2026",
            "source": "test"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/booking-widget/reviews",
            headers=auth_headers,
            json=test_review
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "id" in data, "Created review should have 'id'"
        assert data["guest_name"] == test_review["guest_name"], "Guest name mismatch"
        assert data["rating"] == test_review["rating"], "Rating mismatch"
        assert data["property_id"] == PROPERTY_ID, "Property ID mismatch"
        
        print(f"Created review with ID: {data['id']}")
        
        # Store for cleanup
        TestAdminReviewsCRUD.created_review_id = data["id"]
        return data["id"]
    
    def test_verify_created_review_in_list(self, auth_headers):
        """Verify created review appears in list"""
        if not hasattr(TestAdminReviewsCRUD, 'created_review_id'):
            pytest.skip("No review created to verify")
        
        response = requests.get(
            f"{BASE_URL}/api/booking-widget/reviews/{PROPERTY_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        review_ids = [r.get("id") for r in data]
        assert TestAdminReviewsCRUD.created_review_id in review_ids, "Created review not found in list"
        print(f"Verified review {TestAdminReviewsCRUD.created_review_id} exists in list")
    
    def test_delete_review_requires_auth(self):
        """DELETE /api/booking-widget/reviews/{review_id} requires auth"""
        response = requests.delete(f"{BASE_URL}/api/booking-widget/reviews/fake-id")
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
    
    def test_delete_review_with_auth(self, auth_headers):
        """DELETE /api/booking-widget/reviews/{review_id} deletes review"""
        if not hasattr(TestAdminReviewsCRUD, 'created_review_id'):
            pytest.skip("No review created to delete")
        
        review_id = TestAdminReviewsCRUD.created_review_id
        response = requests.delete(
            f"{BASE_URL}/api/booking-widget/reviews/{review_id}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("status") == "deleted", f"Expected status 'deleted', got {data}"
        print(f"Deleted review {review_id}")
    
    def test_verify_review_deleted(self, auth_headers):
        """Verify deleted review no longer in list"""
        if not hasattr(TestAdminReviewsCRUD, 'created_review_id'):
            pytest.skip("No review to verify deletion")
        
        response = requests.get(
            f"{BASE_URL}/api/booking-widget/reviews/{PROPERTY_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        review_ids = [r.get("id") for r in data]
        assert TestAdminReviewsCRUD.created_review_id not in review_ids, "Deleted review still in list"
        print("Verified review was deleted from list")


class TestRoomPhotoUpload(TestAuth):
    """Test Admin Room Photo Upload endpoints"""
    
    def test_room_photo_upload_requires_auth(self):
        """POST /api/booking-widget/room-photo/{room_id} requires auth"""
        # Create a fake file
        files = {"file": ("test.jpg", b"fake image content", "image/jpeg")}
        response = requests.post(
            f"{BASE_URL}/api/booking-widget/room-photo/standard",
            files=files
        )
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
    
    def test_room_photo_upload_with_auth(self, auth_headers):
        """POST /api/booking-widget/room-photo/{room_id} uploads photo"""
        # Create a minimal valid JPEG (1x1 pixel)
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
            0x00, 0x00, 0x3F, 0x00, 0xFB, 0xD5, 0xDB, 0x20, 0xA8, 0xF1, 0x7E, 0xA9,
            0x00, 0x00, 0x00, 0x00, 0xFF, 0xD9
        ])
        
        files = {"file": ("test_room.jpg", jpeg_bytes, "image/jpeg")}
        response = requests.post(
            f"{BASE_URL}/api/booking-widget/room-photo/standard",
            headers=auth_headers,
            files=files
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("status") == "uploaded", f"Expected status 'uploaded', got {data}"
        assert "url" in data, "Response should contain 'url'"
        assert data["url"].startswith("/api/uploads/rooms/"), f"Invalid URL format: {data['url']}"
        
        print(f"Uploaded room photo: {data['url']}")
        TestRoomPhotoUpload.uploaded_photo_url = data["url"]
    
    def test_room_gallery_upload_requires_auth(self):
        """POST /api/booking-widget/room-gallery/{room_id} requires auth"""
        files = {"file": ("test.jpg", b"fake image content", "image/jpeg")}
        response = requests.post(
            f"{BASE_URL}/api/booking-widget/room-gallery/standard",
            files=files
        )
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
    
    def test_room_gallery_upload_with_auth(self, auth_headers):
        """POST /api/booking-widget/room-gallery/{room_id} uploads to gallery array"""
        # Simple PNG bytes (1x1 transparent pixel)
        png_bytes = bytes([
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 0x00, 0x00, 0x00, 0x0D,
            0x49, 0x48, 0x44, 0x52, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
            0x08, 0x06, 0x00, 0x00, 0x00, 0x1F, 0x15, 0xC4, 0x89, 0x00, 0x00, 0x00,
            0x0A, 0x49, 0x44, 0x41, 0x54, 0x78, 0x9C, 0x63, 0x00, 0x01, 0x00, 0x00,
            0x05, 0x00, 0x01, 0x0D, 0x0A, 0x2D, 0xB4, 0x00, 0x00, 0x00, 0x00, 0x49,
            0x45, 0x4E, 0x44, 0xAE, 0x42, 0x60, 0x82
        ])
        
        files = {"file": ("gallery_test.png", png_bytes, "image/png")}
        response = requests.post(
            f"{BASE_URL}/api/booking-widget/room-gallery/deluxe",
            headers=auth_headers,
            files=files
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("status") == "uploaded", f"Expected status 'uploaded', got {data}"
        assert "url" in data, "Response should contain 'url'"
        assert "gallery" in data["url"], f"Gallery URL should contain 'gallery': {data['url']}"
        
        print(f"Uploaded gallery photo: {data['url']}")


class TestBookingWidgetInfo:
    """Test that booking widget info includes gallery data"""
    
    def test_info_endpoint_returns_reviews(self):
        """GET /api/booking-widget/info returns reviews array"""
        response = requests.get(f"{BASE_URL}/api/booking-widget/info/{PROPERTY_ID}")
        assert response.status_code == 200
        
        data = response.json()
        assert "reviews" in data, "Info should include 'reviews'"
        assert isinstance(data["reviews"], list), "Reviews should be a list"
        assert len(data["reviews"]) >= 1, "Should have at least 1 review"
        
        print(f"Info endpoint returned {len(data['reviews'])} reviews")
    
    def test_info_endpoint_returns_avg_rating(self):
        """GET /api/booking-widget/info returns avg_rating"""
        response = requests.get(f"{BASE_URL}/api/booking-widget/info/{PROPERTY_ID}")
        assert response.status_code == 200
        
        data = response.json()
        assert "avg_rating" in data, "Info should include 'avg_rating'"
        assert isinstance(data["avg_rating"], (int, float)), "avg_rating should be numeric"
        assert 0 <= data["avg_rating"] <= 10, f"avg_rating should be 0-10, got {data['avg_rating']}"
        
        print(f"Average rating: {data['avg_rating']}")
    
    def test_info_endpoint_returns_review_count(self):
        """GET /api/booking-widget/info returns review_count"""
        response = requests.get(f"{BASE_URL}/api/booking-widget/info/{PROPERTY_ID}")
        assert response.status_code == 200
        
        data = response.json()
        assert "review_count" in data, "Info should include 'review_count'"
        assert isinstance(data["review_count"], int), "review_count should be integer"
        
        print(f"Review count: {data['review_count']}")


class TestFullBookingFlow:
    """Test that full booking flow still works with gallery/reviews"""
    
    def test_check_availability(self):
        """POST /api/booking-widget/check-availability works"""
        response = requests.post(f"{BASE_URL}/api/booking-widget/check-availability", json={
            "property_id": PROPERTY_ID,
            "check_in": "2026-02-01",
            "check_out": "2026-02-03"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "available_rooms" in data, "Should return available_rooms"
        assert len(data["available_rooms"]) >= 1, "Should have at least 1 available room"
        
        print(f"Found {len(data['available_rooms'])} available rooms")
    
    def test_create_booking(self):
        """POST /api/booking-widget/book creates booking"""
        response = requests.post(f"{BASE_URL}/api/booking-widget/book", json={
            "property_id": PROPERTY_ID,
            "room_type": "Standard Room",
            "check_in": "2026-02-01",
            "check_out": "2026-02-03",
            "guest_name": "TEST_Iter92_Booking",
            "guest_email": "test_iter92@example.com",
            "guest_phone": "+1234567890",
            "rate": 100,
            "guests": 2,
            "rooms": 1,
            "currency": "GBP"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("status") == "confirmed", f"Expected status 'confirmed', got {data}"
        assert "booking_ref" in data, "Should return booking_ref"
        assert data["booking_ref"].startswith("WEB-"), f"Booking ref should start with WEB-: {data['booking_ref']}"
        
        print(f"Created booking: {data['booking_ref']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
