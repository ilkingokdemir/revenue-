"""
Iteration 91 - Testing Reviews, Per-Room Photos, and Multi-Property Theme Support
Tests for:
1. GET /api/booking-widget/info returns reviews array, avg_rating, review_count, theme object
2. Each room in info response has unique photo URL
3. Check-availability returns photos per room
4. Full booking flow still works
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestBookingWidgetReviewsPhotosTheme:
    """Tests for new reviews, photos, and theme features"""
    
    def test_info_endpoint_returns_reviews_array(self):
        """Verify info endpoint returns reviews array"""
        response = requests.get(f"{BASE_URL}/api/booking-widget/info/vilenza-hotel")
        assert response.status_code == 200
        data = response.json()
        
        # Verify reviews array exists and has items
        assert "reviews" in data, "reviews field missing from response"
        assert isinstance(data["reviews"], list), "reviews should be a list"
        assert len(data["reviews"]) >= 1, "reviews should have at least 1 item"
        
        # Verify review structure
        review = data["reviews"][0]
        assert "guest_name" in review, "review missing guest_name"
        assert "country" in review, "review missing country"
        assert "rating" in review, "review missing rating"
        assert "title" in review, "review missing title"
        assert "comment" in review, "review missing comment"
        assert "date" in review, "review missing date"
        print(f"✓ Reviews array returned with {len(data['reviews'])} reviews")
    
    def test_info_endpoint_returns_avg_rating(self):
        """Verify info endpoint returns avg_rating"""
        response = requests.get(f"{BASE_URL}/api/booking-widget/info/vilenza-hotel")
        assert response.status_code == 200
        data = response.json()
        
        assert "avg_rating" in data, "avg_rating field missing"
        assert isinstance(data["avg_rating"], (int, float)), "avg_rating should be numeric"
        assert 0 <= data["avg_rating"] <= 10, "avg_rating should be between 0 and 10"
        print(f"✓ avg_rating returned: {data['avg_rating']}")
    
    def test_info_endpoint_returns_review_count(self):
        """Verify info endpoint returns review_count"""
        response = requests.get(f"{BASE_URL}/api/booking-widget/info/vilenza-hotel")
        assert response.status_code == 200
        data = response.json()
        
        assert "review_count" in data, "review_count field missing"
        assert isinstance(data["review_count"], int), "review_count should be integer"
        assert data["review_count"] >= 0, "review_count should be non-negative"
        assert data["review_count"] == len(data.get("reviews", [])), "review_count should match reviews array length"
        print(f"✓ review_count returned: {data['review_count']}")
    
    def test_info_endpoint_returns_theme_object(self):
        """Verify info endpoint returns theme object with all required fields"""
        response = requests.get(f"{BASE_URL}/api/booking-widget/info/vilenza-hotel")
        assert response.status_code == 200
        data = response.json()
        
        assert "theme" in data, "theme field missing"
        theme = data["theme"]
        assert isinstance(theme, dict), "theme should be an object"
        
        # Verify theme fields
        assert "accent_color" in theme, "theme missing accent_color"
        assert "hero_image" in theme, "theme missing hero_image"
        assert "tagline" in theme, "theme missing tagline"
        assert "subtitle" in theme, "theme missing subtitle"
        
        # Verify accent_color is a valid hex color
        assert theme["accent_color"].startswith("#"), "accent_color should be hex format"
        
        # Verify hero_image is a URL
        assert theme["hero_image"].startswith("http"), "hero_image should be a URL"
        
        print(f"✓ Theme object returned with accent_color: {theme['accent_color']}")
    
    def test_rooms_have_unique_photos(self):
        """Verify each room has a unique photo URL"""
        response = requests.get(f"{BASE_URL}/api/booking-widget/info/vilenza-hotel")
        assert response.status_code == 200
        data = response.json()
        
        rooms = data.get("rooms", [])
        assert len(rooms) >= 2, "Need at least 2 rooms to test uniqueness"
        
        photos = []
        for room in rooms:
            assert "photo" in room, f"Room {room.get('name')} missing photo field"
            assert room["photo"], f"Room {room.get('name')} has empty photo"
            assert room["photo"].startswith("http"), f"Room {room.get('name')} photo should be URL"
            photos.append(room["photo"])
        
        # Verify photos are unique
        unique_photos = set(photos)
        assert len(unique_photos) == len(photos), f"Photos should be unique. Found {len(photos)} rooms but only {len(unique_photos)} unique photos"
        print(f"✓ All {len(rooms)} rooms have unique photos")
    
    def test_check_availability_returns_photos(self):
        """Verify check-availability returns photos per room"""
        response = requests.post(
            f"{BASE_URL}/api/booking-widget/check-availability",
            json={
                "property_id": "vilenza-hotel",
                "check_in": "2026-02-01",
                "check_out": "2026-02-03"
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        rooms = data.get("available_rooms", [])
        assert len(rooms) >= 1, "Should have at least 1 available room"
        
        for room in rooms:
            assert "photo" in room, f"Room {room.get('name')} missing photo in availability"
            assert room["photo"], f"Room {room.get('name')} has empty photo"
            assert room["photo"].startswith("http"), f"Room photo should be URL"
        
        print(f"✓ Check-availability returns photos for {len(rooms)} rooms")
    
    def test_check_availability_photos_are_unique(self):
        """Verify check-availability returns unique photos per room"""
        response = requests.post(
            f"{BASE_URL}/api/booking-widget/check-availability",
            json={
                "property_id": "vilenza-hotel",
                "check_in": "2026-02-01",
                "check_out": "2026-02-03"
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        rooms = data.get("available_rooms", [])
        photos = [r.get("photo") for r in rooms if r.get("photo")]
        unique_photos = set(photos)
        
        assert len(unique_photos) == len(photos), "Availability photos should be unique per room"
        print(f"✓ Availability returns {len(unique_photos)} unique photos")
    
    def test_review_rating_values_valid(self):
        """Verify all review ratings are valid (0-10)"""
        response = requests.get(f"{BASE_URL}/api/booking-widget/info/vilenza-hotel")
        assert response.status_code == 200
        data = response.json()
        
        reviews = data.get("reviews", [])
        for i, review in enumerate(reviews):
            rating = review.get("rating", 0)
            assert 0 <= rating <= 10, f"Review {i} has invalid rating: {rating}"
        
        print(f"✓ All {len(reviews)} reviews have valid ratings")
    
    def test_avg_rating_calculation_correct(self):
        """Verify avg_rating is correctly calculated from reviews"""
        response = requests.get(f"{BASE_URL}/api/booking-widget/info/vilenza-hotel")
        assert response.status_code == 200
        data = response.json()
        
        reviews = data.get("reviews", [])
        if reviews:
            expected_avg = round(sum(r.get("rating", 0) for r in reviews) / len(reviews), 1)
            actual_avg = data.get("avg_rating", 0)
            assert abs(expected_avg - actual_avg) < 0.2, f"avg_rating {actual_avg} doesn't match calculated {expected_avg}"
        
        print(f"✓ avg_rating {data.get('avg_rating')} is correctly calculated")
    
    def test_full_booking_flow_still_works(self):
        """Verify full booking flow works with new features"""
        # Step 1: Get info
        info_response = requests.get(f"{BASE_URL}/api/booking-widget/info/vilenza-hotel")
        assert info_response.status_code == 200
        info = info_response.json()
        assert "reviews" in info and "theme" in info
        
        # Step 2: Check availability
        avail_response = requests.post(
            f"{BASE_URL}/api/booking-widget/check-availability",
            json={
                "property_id": "vilenza-hotel",
                "check_in": "2026-03-01",
                "check_out": "2026-03-03"
            }
        )
        assert avail_response.status_code == 200
        avail = avail_response.json()
        rooms = avail.get("available_rooms", [])
        assert len(rooms) >= 1
        
        # Step 3: Create booking
        import uuid
        test_email = f"test_iter91_{uuid.uuid4().hex[:6]}@example.com"
        book_response = requests.post(
            f"{BASE_URL}/api/booking-widget/book",
            json={
                "property_id": "vilenza-hotel",
                "room_type": rooms[0]["name"],
                "check_in": "2026-03-01",
                "check_out": "2026-03-03",
                "guest_name": "Test Guest Iter91",
                "guest_email": test_email,
                "rate": rooms[0]["base_rate"],
                "guests": 2,
                "rooms": 1
            }
        )
        assert book_response.status_code == 200
        booking = book_response.json()
        assert booking.get("status") == "confirmed"
        assert booking.get("booking_ref", "").startswith("WEB-")
        
        print(f"✓ Full booking flow works. Ref: {booking.get('booking_ref')}")
    
    def test_theme_defaults_applied(self):
        """Verify theme defaults are applied correctly"""
        response = requests.get(f"{BASE_URL}/api/booking-widget/info/vilenza-hotel")
        assert response.status_code == 200
        data = response.json()
        
        theme = data.get("theme", {})
        # Default accent color should be #1a3c5e
        assert theme.get("accent_color") == "#1a3c5e", f"Default accent_color should be #1a3c5e, got {theme.get('accent_color')}"
        
        # Hero image should be a valid URL
        assert "unsplash.com" in theme.get("hero_image", ""), "Default hero_image should be from Unsplash"
        
        print(f"✓ Theme defaults applied correctly")


class TestReviewsDataStructure:
    """Tests for review data structure and content"""
    
    def test_reviews_have_all_required_fields(self):
        """Verify each review has all required fields"""
        response = requests.get(f"{BASE_URL}/api/booking-widget/info/vilenza-hotel")
        assert response.status_code == 200
        data = response.json()
        
        required_fields = ["guest_name", "country", "rating", "title", "comment", "date"]
        reviews = data.get("reviews", [])
        
        for i, review in enumerate(reviews):
            for field in required_fields:
                assert field in review, f"Review {i} missing field: {field}"
                assert review[field] is not None, f"Review {i} has null {field}"
        
        print(f"✓ All {len(reviews)} reviews have required fields")
    
    def test_six_default_reviews_seeded(self):
        """Verify 6 default reviews are seeded"""
        response = requests.get(f"{BASE_URL}/api/booking-widget/info/vilenza-hotel")
        assert response.status_code == 200
        data = response.json()
        
        reviews = data.get("reviews", [])
        assert len(reviews) == 6, f"Expected 6 default reviews, got {len(reviews)}"
        
        print(f"✓ 6 default reviews seeded correctly")


class TestRoomPhotosConsistency:
    """Tests for room photo consistency between endpoints"""
    
    def test_info_and_availability_photos_match(self):
        """Verify photos are consistent between info and availability endpoints"""
        # Get info
        info_response = requests.get(f"{BASE_URL}/api/booking-widget/info/vilenza-hotel")
        assert info_response.status_code == 200
        info = info_response.json()
        
        # Get availability
        avail_response = requests.post(
            f"{BASE_URL}/api/booking-widget/check-availability",
            json={
                "property_id": "vilenza-hotel",
                "check_in": "2026-02-01",
                "check_out": "2026-02-03"
            }
        )
        assert avail_response.status_code == 200
        avail = avail_response.json()
        
        # Build photo map from info
        info_photos = {r.get("name"): r.get("photo") for r in info.get("rooms", [])}
        
        # Verify availability photos match
        for room in avail.get("available_rooms", []):
            room_name = room.get("name")
            if room_name in info_photos:
                assert room.get("photo") == info_photos[room_name], f"Photo mismatch for {room_name}"
        
        print(f"✓ Photos consistent between info and availability endpoints")
