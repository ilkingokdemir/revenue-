"""
Iteration 210 - Housekeeping Route Optimizer + ESG Public Badge Tests

Tests:
1. GET /api/housekeeping/route/{property_id} - Returns optimized cleaning route
2. GET /api/housekeeping/route/{property_id}?assigned_to=X - Filters by cleaner
3. GET /api/esg/{property_id}/public-badge - Public ESG badge (no auth)
4. PUT /api/housekeeping/rooms/{id}/status - Mark room clean
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
PROPERTY_ID = "aldgate-flats"


class TestHousekeepingRouteOptimizer:
    """Housekeeping Route Optimizer endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        self.session = requests.Session()
        login_resp = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        self.token = login_resp.json().get("token") or login_resp.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_get_housekeeping_route_success(self):
        """GET /api/housekeeping/route/{property_id} returns route data"""
        resp = self.session.get(f"{BASE_URL}/api/housekeeping/route/{PROPERTY_ID}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        # Verify response structure
        assert "rounds" in data, "Missing 'rounds' in response"
        assert "total_rooms" in data, "Missing 'total_rooms' in response"
        assert "total_estimated_minutes" in data, "Missing 'total_estimated_minutes' in response"
        assert "checkouts" in data, "Missing 'checkouts' in response"
        assert "arrivals" in data, "Missing 'arrivals' in response"
        assert "stayovers" in data, "Missing 'stayovers' in response"
        assert "vip_count" in data, "Missing 'vip_count' in response"
        assert "as_of" in data, "Missing 'as_of' in response"
        
        # Verify rounds structure if any exist
        if data["rounds"]:
            room = data["rounds"][0]
            assert "position" in room, "Missing 'position' in room"
            assert "room_id" in room, "Missing 'room_id' in room"
            assert "room_number" in room, "Missing 'room_number' in room"
            assert "floor" in room, "Missing 'floor' in room"
            assert "status" in room, "Missing 'status' in room"
            assert "kind" in room, "Missing 'kind' in room"
            assert "tags" in room, "Missing 'tags' in room"
            assert "score" in room, "Missing 'score' in room"
            assert "estimated_minutes" in room, "Missing 'estimated_minutes' in room"
            assert "eta_minutes_from_start" in room, "Missing 'eta_minutes_from_start' in room"
        
        print(f"Route returned {data['total_rooms']} rooms, {data['checkouts']} checkouts, {data['arrivals']} arrivals")
    
    def test_get_housekeeping_route_with_assigned_to_filter(self):
        """GET /api/housekeeping/route/{property_id}?assigned_to=X filters by cleaner"""
        resp = self.session.get(
            f"{BASE_URL}/api/housekeeping/route/{PROPERTY_ID}",
            params={"assigned_to": "Some Cleaner"}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "rounds" in data
        # If any rooms returned, they should all be assigned to "Some Cleaner"
        for room in data["rounds"]:
            assert room.get("assigned_to") == "Some Cleaner", f"Room {room['room_number']} not assigned to 'Some Cleaner'"
        
        print(f"Filtered route returned {data['total_rooms']} rooms for 'Some Cleaner'")
    
    def test_get_housekeeping_route_empty_state_valid(self):
        """Empty route (all rooms clean) is a valid state"""
        resp = self.session.get(f"{BASE_URL}/api/housekeeping/route/{PROPERTY_ID}")
        assert resp.status_code == 200
        
        data = resp.json()
        # Empty state is valid - all rooms might be clean
        if data["total_rooms"] == 0:
            assert data["rounds"] == [], "Rounds should be empty list when no rooms need cleaning"
            assert data["checkouts"] == 0
            assert data["arrivals"] == 0
            assert data["stayovers"] == 0
            print("Empty route state verified - all rooms are clean")
        else:
            print(f"Route has {data['total_rooms']} rooms to clean")


class TestESGPublicBadge:
    """ESG Public Badge endpoint tests (no auth required)"""
    
    def test_get_public_badge_success(self):
        """GET /api/esg/{property_id}/public-badge returns badge data (no auth)"""
        # No auth required for public badge
        resp = requests.get(f"{BASE_URL}/api/esg/{PROPERTY_ID}/public-badge")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        # Verify response structure
        assert "score" in data, "Missing 'score' in response"
        assert "grade" in data, "Missing 'grade' in response"
        assert "show_badge" in data, "Missing 'show_badge' in response"
        assert "active_initiatives" in data, "Missing 'active_initiatives' in response"
        assert "highlight_initiatives" in data, "Missing 'highlight_initiatives' in response"
        
        # Verify data types
        assert isinstance(data["score"], (int, float)), "Score should be numeric"
        assert isinstance(data["grade"], str), "Grade should be string"
        assert isinstance(data["show_badge"], bool), "show_badge should be boolean"
        assert isinstance(data["active_initiatives"], int), "active_initiatives should be int"
        assert isinstance(data["highlight_initiatives"], list), "highlight_initiatives should be list"
        
        print(f"ESG Badge: score={data['score']}, grade={data['grade']}, show_badge={data['show_badge']}")
        print(f"Active initiatives: {data['active_initiatives']}, highlights: {data['highlight_initiatives']}")
    
    def test_public_badge_show_badge_threshold(self):
        """show_badge=true only when score >= 65"""
        resp = requests.get(f"{BASE_URL}/api/esg/{PROPERTY_ID}/public-badge")
        assert resp.status_code == 200
        
        data = resp.json()
        score = data["score"]
        show_badge = data["show_badge"]
        
        if score >= 65:
            assert show_badge is True, f"show_badge should be True when score={score} >= 65"
            print(f"Score {score} >= 65: show_badge=True (correct)")
        else:
            assert show_badge is False, f"show_badge should be False when score={score} < 65"
            print(f"Score {score} < 65: show_badge=False (correct)")
    
    def test_public_badge_grade_mapping(self):
        """Grade should match score thresholds"""
        resp = requests.get(f"{BASE_URL}/api/esg/{PROPERTY_ID}/public-badge")
        assert resp.status_code == 200
        
        data = resp.json()
        score = data["score"]
        grade = data["grade"]
        
        # Verify grade mapping
        if score >= 90:
            assert grade == "A+", f"Score {score} should be A+, got {grade}"
        elif score >= 80:
            assert grade == "A", f"Score {score} should be A, got {grade}"
        elif score >= 65:
            assert grade == "B", f"Score {score} should be B, got {grade}"
        elif score >= 50:
            assert grade == "C", f"Score {score} should be C, got {grade}"
        else:
            assert grade == "D", f"Score {score} should be D, got {grade}"
        
        print(f"Grade mapping verified: score={score} -> grade={grade}")
    
    def test_public_badge_nonexistent_property(self):
        """Public badge for non-existent property returns default/empty data"""
        resp = requests.get(f"{BASE_URL}/api/esg/nonexistent-property-xyz/public-badge")
        # Should still return 200 with default values (no initiatives active)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
        data = resp.json()
        assert "score" in data
        assert "show_badge" in data
        print(f"Non-existent property badge: score={data['score']}, show_badge={data['show_badge']}")


class TestMarkRoomClean:
    """Test marking room as clean via PUT /api/housekeeping/rooms/{id}/status"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        self.session = requests.Session()
        login_resp = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        self.token = login_resp.json().get("token") or login_resp.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_mark_room_clean(self):
        """PUT /api/housekeeping/rooms/{id}/status marks room as clean"""
        # First get rooms to find one to mark clean
        rooms_resp = self.session.get(f"{BASE_URL}/api/housekeeping/rooms/{PROPERTY_ID}")
        assert rooms_resp.status_code == 200
        
        rooms = rooms_resp.json()
        if not rooms:
            pytest.skip("No rooms available to test mark clean")
        
        # Find a dirty or in_progress room, or use first room
        target_room = None
        for room in rooms:
            if room.get("status") in ["dirty", "in_progress"]:
                target_room = room
                break
        
        if not target_room:
            target_room = rooms[0]
        
        room_id = target_room["id"]
        original_status = target_room.get("status")
        
        # Mark as clean
        update_resp = self.session.put(
            f"{BASE_URL}/api/housekeeping/rooms/{room_id}/status",
            json={"status": "clean"}
        )
        assert update_resp.status_code == 200, f"Expected 200, got {update_resp.status_code}: {update_resp.text}"
        
        updated_room = update_resp.json()
        assert updated_room.get("status") == "clean", f"Room status should be 'clean', got {updated_room.get('status')}"
        assert "last_cleaned_at" in updated_room, "Missing 'last_cleaned_at' after marking clean"
        
        print(f"Room {target_room['room_number']} marked clean (was: {original_status})")
        
        # Restore original status if it wasn't clean
        if original_status and original_status != "clean":
            self.session.put(
                f"{BASE_URL}/api/housekeeping/rooms/{room_id}/status",
                json={"status": original_status}
            )
            print(f"Restored room {target_room['room_number']} to {original_status}")


class TestRegressionExistingPanels:
    """Regression tests for existing panels"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        self.session = requests.Session()
        login_resp = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        self.token = login_resp.json().get("token") or login_resp.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_housekeeping_rooms_endpoint(self):
        """GET /api/housekeeping/rooms/{property_id} still works"""
        resp = self.session.get(f"{BASE_URL}/api/housekeeping/rooms/{PROPERTY_ID}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        print(f"Housekeeping rooms endpoint: {len(resp.json())} rooms")
    
    def test_esg_dashboard_endpoint(self):
        """GET /api/esg/{property_id}/dashboard still works"""
        resp = self.session.get(f"{BASE_URL}/api/esg/{PROPERTY_ID}/dashboard")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert "esg_score" in data
        print(f"ESG Dashboard: score={data['esg_score']}, grade={data['grade']}")
    
    def test_group_bookings_endpoint(self):
        """GET /api/group-booking/requests/{property_id} still works"""
        resp = self.session.get(f"{BASE_URL}/api/group-booking/requests/{PROPERTY_ID}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        print(f"Group bookings endpoint: {len(resp.json())} requests")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
