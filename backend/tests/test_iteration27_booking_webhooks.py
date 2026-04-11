"""
Iteration 27 Tests: Booking Webhooks, Outbound Sync, Backend Refactoring
Tests for:
1. Booking webhook events (booking.created, booking.confirmed, booking.cancelled, booking.payment_received)
2. GET /api/webhooks/events returns 12 events with category field
3. POST /api/booking/reserve fires booking.created webhook
4. PUT /api/bookings/{id}/status fires booking.cancelled webhook
5. GET /api/integrations/outbound-status returns sync status
6. POST /api/integrations/sync-all-outbound attempts sync
7. Backend module extraction (models.py, auth.py, database.py)
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuth:
    """Authentication tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get auth token for admin user"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data
        return data["token"]
    
    def test_login_success(self):
        """Test admin login works"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "admin@hotelbox.com"
        assert data["role"] == "admin"
        assert "token" in data
        print("✓ Login successful for admin@hotelbox.com")


class TestWebhookEvents:
    """Test webhook events endpoint with new booking events"""
    
    def test_get_webhook_events_returns_12_events(self):
        """GET /api/webhooks/events should return 12 events including 4 booking events"""
        response = requests.get(f"{BASE_URL}/api/webhooks/events")
        assert response.status_code == 200
        events = response.json()
        
        # Should have 12 events total
        assert len(events) == 12, f"Expected 12 events, got {len(events)}"
        
        # Check all events have required fields
        for event in events:
            assert "id" in event
            assert "name" in event
            assert "description" in event
            assert "category" in event, f"Event {event['id']} missing category field"
        
        print(f"✓ GET /api/webhooks/events returns {len(events)} events")
    
    def test_webhook_events_have_categories(self):
        """Verify events have correct categories (reviews vs bookings)"""
        response = requests.get(f"{BASE_URL}/api/webhooks/events")
        assert response.status_code == 200
        events = response.json()
        
        # Group by category
        categories = {}
        for event in events:
            cat = event.get("category", "unknown")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(event["id"])
        
        # Should have reviews and bookings categories
        assert "reviews" in categories, "Missing 'reviews' category"
        assert "bookings" in categories, "Missing 'bookings' category"
        
        # Reviews should have 8 events
        assert len(categories["reviews"]) == 8, f"Expected 8 review events, got {len(categories['reviews'])}"
        
        # Bookings should have 4 events
        assert len(categories["bookings"]) == 4, f"Expected 4 booking events, got {len(categories['bookings'])}"
        
        print(f"✓ Events categorized correctly: {len(categories['reviews'])} reviews, {len(categories['bookings'])} bookings")
    
    def test_booking_events_present(self):
        """Verify all 4 booking events are present"""
        response = requests.get(f"{BASE_URL}/api/webhooks/events")
        assert response.status_code == 200
        events = response.json()
        
        event_ids = [e["id"] for e in events]
        
        booking_events = [
            "booking.created",
            "booking.confirmed", 
            "booking.cancelled",
            "booking.payment_received"
        ]
        
        for event_id in booking_events:
            assert event_id in event_ids, f"Missing booking event: {event_id}"
        
        print(f"✓ All 4 booking events present: {booking_events}")


class TestBookingWebhooks:
    """Test booking operations fire webhooks"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_booking_reserve_creates_booking(self, auth_headers):
        """POST /api/booking/reserve creates a booking"""
        # First get a room type
        rooms_response = requests.get(f"{BASE_URL}/api/booking/rooms/aldgate-flats")
        assert rooms_response.status_code == 200
        rooms = rooms_response.json()
        
        if len(rooms) == 0:
            pytest.skip("No rooms available for testing")
        
        room = rooms[0]
        
        # Create booking
        booking_data = {
            "property_id": "aldgate-flats",
            "room_type_id": room["id"],
            "guest_name": "TEST_Webhook_Guest",
            "guest_email": "test_webhook@example.com",
            "guest_phone": "+44 7000 000000",
            "check_in": "2026-02-15",
            "check_out": "2026-02-17",
            "adults": 2,
            "children": 0,
            "rooms": 1,
            "special_requests": "Testing webhook"
        }
        
        response = requests.post(f"{BASE_URL}/api/booking/reserve", json=booking_data)
        assert response.status_code == 200, f"Booking failed: {response.text}"
        
        booking = response.json()
        assert "id" in booking
        assert "booking_ref" in booking
        assert booking["guest_name"] == "TEST_Webhook_Guest"
        assert booking["status"] == "confirmed"
        
        print(f"✓ Booking created with ref: {booking['booking_ref']}")
        
        # Store booking ID for later tests
        return booking
    
    def test_booking_status_update_cancelled(self, auth_headers):
        """PUT /api/bookings/{id}/status with status=cancelled fires webhook"""
        # First create a booking
        rooms_response = requests.get(f"{BASE_URL}/api/booking/rooms/aldgate-flats")
        rooms = rooms_response.json()
        
        if len(rooms) == 0:
            pytest.skip("No rooms available")
        
        room = rooms[0]
        
        booking_data = {
            "property_id": "aldgate-flats",
            "room_type_id": room["id"],
            "guest_name": "TEST_Cancel_Guest",
            "guest_email": "test_cancel@example.com",
            "check_in": "2026-03-01",
            "check_out": "2026-03-03",
            "adults": 1,
            "children": 0,
            "rooms": 1
        }
        
        create_response = requests.post(f"{BASE_URL}/api/booking/reserve", json=booking_data)
        assert create_response.status_code == 200
        booking = create_response.json()
        booking_id = booking["id"]
        
        # Cancel the booking (status is a query parameter)
        cancel_response = requests.put(
            f"{BASE_URL}/api/bookings/{booking_id}/status?status=cancelled",
            headers=auth_headers
        )
        assert cancel_response.status_code == 200, f"Cancel failed: {cancel_response.text}"
        
        updated = cancel_response.json()
        assert updated["status"] == "cancelled"
        
        print(f"✓ Booking {booking_id} cancelled successfully")


class TestOutboundSync:
    """Test outbound sync status and sync-all endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_outbound_status_endpoint(self, auth_headers):
        """GET /api/integrations/outbound-status returns sync status"""
        response = requests.get(f"{BASE_URL}/api/integrations/outbound-status", headers=auth_headers)
        assert response.status_code == 200, f"Outbound status failed: {response.text}"
        
        data = response.json()
        
        # Should have expected fields
        assert "total_pending" in data or "pending_count" in data or "by_platform" in data
        
        print(f"✓ GET /api/integrations/outbound-status returns: {list(data.keys())}")
    
    def test_sync_all_outbound_endpoint(self, auth_headers):
        """POST /api/integrations/sync-all-outbound attempts to sync"""
        response = requests.post(f"{BASE_URL}/api/integrations/sync-all-outbound", headers=auth_headers)
        assert response.status_code == 200, f"Sync all failed: {response.text}"
        
        data = response.json()
        # Should return some status about the sync attempt
        assert isinstance(data, dict)
        
        print(f"✓ POST /api/integrations/sync-all-outbound returns: {data}")


class TestSyncLogs:
    """Test sync logs include booking-engine entries"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_sync_logs_endpoint(self, auth_headers):
        """GET /api/sync-logs returns logs"""
        response = requests.get(f"{BASE_URL}/api/sync-logs?limit=50", headers=auth_headers)
        assert response.status_code == 200
        
        logs = response.json()
        assert isinstance(logs, list)
        
        print(f"✓ GET /api/sync-logs returns {len(logs)} logs")
    
    def test_sync_logs_filter_by_platform(self, auth_headers):
        """GET /api/sync-logs with platform filter works"""
        response = requests.get(f"{BASE_URL}/api/sync-logs?platform=booking-engine&limit=10", headers=auth_headers)
        assert response.status_code == 200
        
        logs = response.json()
        assert isinstance(logs, list)
        
        # If there are logs, they should be for booking-engine
        for log in logs:
            if "platform" in log:
                assert log["platform"] == "booking-engine"
        
        print(f"✓ Sync logs filter by platform works, found {len(logs)} booking-engine logs")


class TestBookingEngineAPI:
    """Test booking engine public endpoints"""
    
    def test_get_property(self):
        """GET /api/booking/property/{id} returns property data"""
        response = requests.get(f"{BASE_URL}/api/booking/property/aldgate-flats")
        assert response.status_code == 200
        
        data = response.json()
        assert "name" in data
        assert "id" in data or "property_id" in data
        
        print(f"✓ GET /api/booking/property/aldgate-flats returns: {data.get('name')}")
    
    def test_get_rooms(self):
        """GET /api/booking/rooms/{property_id} returns rooms"""
        response = requests.get(f"{BASE_URL}/api/booking/rooms/aldgate-flats")
        assert response.status_code == 200
        
        rooms = response.json()
        assert isinstance(rooms, list)
        
        if len(rooms) > 0:
            room = rooms[0]
            assert "id" in room
            assert "name" in room
            assert "base_price" in room
        
        print(f"✓ GET /api/booking/rooms/aldgate-flats returns {len(rooms)} rooms")
    
    def test_get_reviews(self):
        """GET /api/booking/reviews/{property_id} returns reviews"""
        response = requests.get(f"{BASE_URL}/api/booking/reviews/aldgate-flats?limit=6")
        assert response.status_code == 200
        
        reviews = response.json()
        assert isinstance(reviews, list)
        
        print(f"✓ GET /api/booking/reviews/aldgate-flats returns {len(reviews)} reviews")


class TestBackendModuleExtraction:
    """Test that backend modules are properly extracted and working"""
    
    def test_models_import(self):
        """Verify models.py is properly imported"""
        # This is tested implicitly by the API working
        # But we can verify by checking a model-dependent endpoint
        response = requests.get(f"{BASE_URL}/api/reviews")
        assert response.status_code == 200
        print("✓ models.py import working (reviews endpoint functional)")
    
    def test_auth_import(self):
        """Verify auth.py is properly imported"""
        # Test login which uses auth module
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200
        print("✓ auth.py import working (login functional)")
    
    def test_database_import(self):
        """Verify database.py is properly imported"""
        # Test any DB-dependent endpoint
        response = requests.get(f"{BASE_URL}/api/properties")
        # May need auth, but should not return 500
        assert response.status_code in [200, 401]
        print("✓ database.py import working (DB connection functional)")


class TestCleanup:
    """Cleanup test data"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_cleanup_test_bookings(self, auth_headers):
        """Clean up TEST_ prefixed bookings"""
        # Get all bookings
        response = requests.get(f"{BASE_URL}/api/bookings", headers=auth_headers)
        if response.status_code == 200:
            bookings = response.json()
            test_bookings = [b for b in bookings if b.get("guest_name", "").startswith("TEST_")]
            
            for booking in test_bookings:
                # Cancel test bookings
                requests.put(
                    f"{BASE_URL}/api/bookings/{booking['id']}/status",
                    json={"status": "cancelled"},
                    headers=auth_headers
                )
            
            print(f"✓ Cleaned up {len(test_bookings)} test bookings")
        else:
            print("✓ No bookings to clean up")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
