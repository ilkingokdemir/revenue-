"""
Iteration 87 - Testing 3 New Modules:
1. My Tasks Dashboard - Personalized daily overview
2. Lost & Found Module - Track lost items with claim/dispose workflow
3. Event & Meeting Room Management - Rooms, bookings, catering
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
STAFF_EMAIL = "ali@hotel.com"
STAFF_PASSWORD = "Staff2026!"


@pytest.fixture(scope="module")
def admin_session():
    """Get authenticated admin session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    response = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code != 200:
        pytest.skip(f"Admin login failed: {response.status_code} - {response.text}")
    return session


@pytest.fixture(scope="module")
def staff_session():
    """Get authenticated staff session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    response = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": STAFF_EMAIL,
        "password": STAFF_PASSWORD
    })
    if response.status_code != 200:
        pytest.skip(f"Staff login failed: {response.status_code} - {response.text}")
    return session


class TestMyTasksDashboard:
    """My Tasks - Personalized daily overview aggregating shifts, handovers, routines, maintenance"""
    
    def test_my_tasks_endpoint_returns_200(self, admin_session):
        """GET /api/my-tasks returns 200 for authenticated user"""
        response = admin_session.get(f"{BASE_URL}/api/my-tasks")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("PASS: GET /api/my-tasks returns 200")
    
    def test_my_tasks_returns_user_info(self, admin_session):
        """GET /api/my-tasks returns user info"""
        response = admin_session.get(f"{BASE_URL}/api/my-tasks")
        data = response.json()
        assert "user" in data, "Response should contain 'user' field"
        assert "name" in data["user"], "User should have 'name'"
        assert "role" in data["user"], "User should have 'role'"
        assert "email" in data["user"], "User should have 'email'"
        print(f"PASS: User info returned - {data['user']['name']} ({data['user']['role']})")
    
    def test_my_tasks_returns_date(self, admin_session):
        """GET /api/my-tasks returns current date"""
        response = admin_session.get(f"{BASE_URL}/api/my-tasks")
        data = response.json()
        assert "date" in data, "Response should contain 'date' field"
        print(f"PASS: Date returned - {data['date']}")
    
    def test_my_tasks_returns_aggregated_data(self, admin_session):
        """GET /api/my-tasks returns all aggregated data fields"""
        response = admin_session.get(f"{BASE_URL}/api/my-tasks")
        data = response.json()
        
        # Check all expected fields
        expected_fields = ["today_shifts", "week_shifts", "handover_notes", "routines", 
                          "maintenance", "compliance", "unread_notifications", "summary"]
        for field in expected_fields:
            assert field in data, f"Response should contain '{field}' field"
        
        print(f"PASS: All aggregated data fields present: {expected_fields}")
    
    def test_my_tasks_returns_summary_stats(self, admin_session):
        """GET /api/my-tasks returns summary statistics"""
        response = admin_session.get(f"{BASE_URL}/api/my-tasks")
        data = response.json()
        
        summary = data.get("summary", {})
        expected_stats = ["shifts_today", "shifts_this_week", "pending_handovers", 
                         "active_routines", "open_maintenance", "upcoming_compliance"]
        for stat in expected_stats:
            assert stat in summary, f"Summary should contain '{stat}'"
        
        print(f"PASS: Summary stats present - shifts_today={summary['shifts_today']}, pending_handovers={summary['pending_handovers']}")
    
    def test_my_tasks_staff_access(self, staff_session):
        """Staff user can access /api/my-tasks"""
        response = staff_session.get(f"{BASE_URL}/api/my-tasks")
        assert response.status_code == 200, f"Staff should access my-tasks: {response.status_code}"
        data = response.json()
        assert data["user"]["email"] == STAFF_EMAIL
        print(f"PASS: Staff user ({STAFF_EMAIL}) can access my-tasks")


class TestLostFoundModule:
    """Lost & Found - Track lost items, claim/dispose workflow"""
    
    def test_lost_found_list_returns_200(self, admin_session):
        """GET /api/lost-found/{property_id} returns 200"""
        response = admin_session.get(f"{BASE_URL}/api/lost-found/all")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("PASS: GET /api/lost-found/all returns 200")
    
    def test_lost_found_returns_items_and_stats(self, admin_session):
        """GET /api/lost-found returns items array and stats"""
        response = admin_session.get(f"{BASE_URL}/api/lost-found/all")
        data = response.json()
        
        assert "items" in data, "Response should contain 'items' array"
        assert "stats" in data, "Response should contain 'stats' object"
        assert isinstance(data["items"], list), "Items should be a list"
        
        # Check stats structure
        stats = data["stats"]
        expected_stats = ["total", "unclaimed", "claimed", "disposed"]
        for stat in expected_stats:
            assert stat in stats, f"Stats should contain '{stat}'"
        
        print(f"PASS: Lost & Found returns items ({len(data['items'])}) and stats (total={stats['total']})")
    
    def test_lost_found_create_item(self, admin_session):
        """POST /api/lost-found creates a new item"""
        test_item = {
            "property_id": "aldgate-flats",
            "item_name": f"TEST_Wallet_{uuid.uuid4().hex[:6]}",
            "description": "Black leather wallet with cards",
            "category": "personal",
            "found_location": "Room 305",
            "storage_location": "Reception safe",
            "guest_name": "John Doe",
            "guest_room": "305",
            "found_date": "2026-01-15"
        }
        
        response = admin_session.post(f"{BASE_URL}/api/lost-found", json=test_item)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["item_name"] == test_item["item_name"]
        assert data["status"] == "unclaimed"
        assert "id" in data
        
        print(f"PASS: Created lost item - {data['item_name']} (id={data['id']})")
        return data["id"]
    
    def test_lost_found_status_filter(self, admin_session):
        """GET /api/lost-found with status filter works"""
        response = admin_session.get(f"{BASE_URL}/api/lost-found/all?status=unclaimed")
        assert response.status_code == 200
        data = response.json()
        
        # All items should be unclaimed
        for item in data["items"]:
            assert item["status"] == "unclaimed", f"Item {item['id']} should be unclaimed"
        
        print(f"PASS: Status filter works - {len(data['items'])} unclaimed items")
    
    def test_lost_found_claim_workflow(self, admin_session):
        """PUT /api/lost-found/{id} can claim an item"""
        # First create an item
        test_item = {
            "property_id": "aldgate-flats",
            "item_name": f"TEST_Phone_{uuid.uuid4().hex[:6]}",
            "category": "electronics",
            "found_location": "Lobby"
        }
        create_response = admin_session.post(f"{BASE_URL}/api/lost-found", json=test_item)
        item_id = create_response.json()["id"]
        
        # Claim the item
        claim_response = admin_session.put(f"{BASE_URL}/api/lost-found/{item_id}", json={
            "status": "claimed",
            "claimed_by": "Jane Smith"
        })
        assert claim_response.status_code == 200, f"Claim failed: {claim_response.text}"
        
        claimed_item = claim_response.json()
        assert claimed_item["status"] == "claimed"
        assert claimed_item["claimed_by"] == "Jane Smith"
        assert claimed_item["claimed_date"] != ""
        
        print(f"PASS: Claim workflow works - item claimed by {claimed_item['claimed_by']}")
    
    def test_lost_found_dispose_workflow(self, admin_session):
        """PUT /api/lost-found/{id} can dispose an item"""
        # First create an item
        test_item = {
            "property_id": "aldgate-flats",
            "item_name": f"TEST_Umbrella_{uuid.uuid4().hex[:6]}",
            "category": "other",
            "found_location": "Restaurant"
        }
        create_response = admin_session.post(f"{BASE_URL}/api/lost-found", json=test_item)
        item_id = create_response.json()["id"]
        
        # Dispose the item
        dispose_response = admin_session.put(f"{BASE_URL}/api/lost-found/{item_id}", json={
            "status": "disposed"
        })
        assert dispose_response.status_code == 200, f"Dispose failed: {dispose_response.text}"
        
        disposed_item = dispose_response.json()
        assert disposed_item["status"] == "disposed"
        assert disposed_item["disposed_date"] != ""
        
        print(f"PASS: Dispose workflow works - item disposed")
    
    def test_lost_found_delete_item(self, admin_session):
        """DELETE /api/lost-found/{id} deletes an item"""
        # First create an item
        test_item = {
            "property_id": "aldgate-flats",
            "item_name": f"TEST_Delete_{uuid.uuid4().hex[:6]}",
            "category": "other"
        }
        create_response = admin_session.post(f"{BASE_URL}/api/lost-found", json=test_item)
        item_id = create_response.json()["id"]
        
        # Delete the item
        delete_response = admin_session.delete(f"{BASE_URL}/api/lost-found/{item_id}")
        assert delete_response.status_code == 200, f"Delete failed: {delete_response.text}"
        
        # Verify deletion
        list_response = admin_session.get(f"{BASE_URL}/api/lost-found/all")
        items = list_response.json()["items"]
        item_ids = [i["id"] for i in items]
        assert item_id not in item_ids, "Item should be deleted"
        
        print(f"PASS: Delete works - item {item_id} removed")


class TestEventsModule:
    """Event & Meeting Room Management - Rooms, bookings, catering"""
    
    # ==================== MEETING ROOMS ====================
    
    def test_event_rooms_list_returns_200(self, admin_session):
        """GET /api/events/rooms/{property_id} returns 200"""
        response = admin_session.get(f"{BASE_URL}/api/events/rooms/all")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"PASS: GET /api/events/rooms/all returns 200 ({len(response.json())} rooms)")
    
    def test_event_rooms_create(self, admin_session):
        """POST /api/events/rooms creates a new room"""
        test_room = {
            "property_id": "aldgate-flats",
            "name": f"TEST_Conference_{uuid.uuid4().hex[:6]}",
            "capacity": 20,
            "floor": "2",
            "hourly_rate": 50,
            "half_day_rate": 150,
            "full_day_rate": 250,
            "equipment": ["Projector", "Whiteboard", "Video conferencing"],
            "amenities": ["WiFi", "Air conditioning"]
        }
        
        response = admin_session.post(f"{BASE_URL}/api/events/rooms", json=test_room)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["name"] == test_room["name"]
        assert data["capacity"] == 20
        assert data["hourly_rate"] == 50
        assert data["half_day_rate"] == 150
        assert data["full_day_rate"] == 250
        assert "id" in data
        
        print(f"PASS: Created room - {data['name']} (capacity={data['capacity']}, rates: £{data['hourly_rate']}/hr)")
        return data["id"]
    
    def test_event_rooms_update(self, admin_session):
        """PUT /api/events/rooms/{id} updates a room"""
        # First create a room
        test_room = {
            "property_id": "aldgate-flats",
            "name": f"TEST_Update_{uuid.uuid4().hex[:6]}",
            "capacity": 10,
            "hourly_rate": 30
        }
        create_response = admin_session.post(f"{BASE_URL}/api/events/rooms", json=test_room)
        room_id = create_response.json()["id"]
        
        # Update the room
        update_response = admin_session.put(f"{BASE_URL}/api/events/rooms/{room_id}", json={
            "capacity": 15,
            "hourly_rate": 40
        })
        assert update_response.status_code == 200, f"Update failed: {update_response.text}"
        
        updated_room = update_response.json()
        assert updated_room["capacity"] == 15
        assert updated_room["hourly_rate"] == 40
        
        print(f"PASS: Room updated - capacity={updated_room['capacity']}, rate=£{updated_room['hourly_rate']}")
    
    def test_event_rooms_delete(self, admin_session):
        """DELETE /api/events/rooms/{id} deletes a room"""
        # First create a room
        test_room = {
            "property_id": "aldgate-flats",
            "name": f"TEST_Delete_{uuid.uuid4().hex[:6]}",
            "capacity": 5
        }
        create_response = admin_session.post(f"{BASE_URL}/api/events/rooms", json=test_room)
        room_id = create_response.json()["id"]
        
        # Delete the room
        delete_response = admin_session.delete(f"{BASE_URL}/api/events/rooms/{room_id}")
        assert delete_response.status_code == 200, f"Delete failed: {delete_response.text}"
        
        print(f"PASS: Room deleted - {room_id}")
    
    # ==================== EVENT BOOKINGS ====================
    
    def test_event_bookings_list_returns_200(self, admin_session):
        """GET /api/events/bookings/{property_id} returns 200"""
        response = admin_session.get(f"{BASE_URL}/api/events/bookings/all")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"PASS: GET /api/events/bookings/all returns 200 ({len(response.json())} bookings)")
    
    def test_event_bookings_create(self, admin_session):
        """POST /api/events/bookings creates a new booking"""
        # First get a room
        rooms_response = admin_session.get(f"{BASE_URL}/api/events/rooms/all")
        rooms = rooms_response.json()
        room_id = rooms[0]["id"] if rooms else "test-room"
        room_name = rooms[0]["name"] if rooms else "Test Room"
        
        test_booking = {
            "property_id": "aldgate-flats",
            "room_id": room_id,
            "room_name": room_name,
            "event_name": f"TEST_Meeting_{uuid.uuid4().hex[:6]}",
            "organizer": "John Smith",
            "contact_email": "john@example.com",
            "date": "2026-02-15",
            "start_time": "09:00",
            "end_time": "12:00",
            "attendees": 15,
            "setup_type": "boardroom",
            "catering": "Morning Break",
            "total_cost": 350
        }
        
        response = admin_session.post(f"{BASE_URL}/api/events/bookings", json=test_booking)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["event_name"] == test_booking["event_name"]
        assert data["attendees"] == 15
        assert data["setup_type"] == "boardroom"
        assert data["catering"] == "Morning Break"
        assert data["total_cost"] == 350
        assert data["status"] == "confirmed"
        assert "id" in data
        
        print(f"PASS: Created booking - {data['event_name']} ({data['attendees']} attendees, £{data['total_cost']})")
        return data["id"]
    
    def test_event_bookings_setup_types(self, admin_session):
        """Event bookings support all setup types"""
        setup_types = ["theater", "classroom", "boardroom", "cocktail", "banquet", "ushape"]
        
        for setup_type in setup_types:
            test_booking = {
                "property_id": "aldgate-flats",
                "event_name": f"TEST_{setup_type}_{uuid.uuid4().hex[:4]}",
                "date": "2026-03-01",
                "setup_type": setup_type,
                "attendees": 10
            }
            response = admin_session.post(f"{BASE_URL}/api/events/bookings", json=test_booking)
            assert response.status_code == 200, f"Setup type {setup_type} failed: {response.text}"
            assert response.json()["setup_type"] == setup_type
        
        print(f"PASS: All setup types supported - {setup_types}")
    
    def test_event_bookings_update_status(self, admin_session):
        """PUT /api/events/bookings/{id} can update status"""
        # First create a booking
        test_booking = {
            "property_id": "aldgate-flats",
            "event_name": f"TEST_Status_{uuid.uuid4().hex[:6]}",
            "date": "2026-02-20",
            "attendees": 5
        }
        create_response = admin_session.post(f"{BASE_URL}/api/events/bookings", json=test_booking)
        booking_id = create_response.json()["id"]
        
        # Update to completed
        update_response = admin_session.put(f"{BASE_URL}/api/events/bookings/{booking_id}", json={
            "status": "completed"
        })
        assert update_response.status_code == 200
        assert update_response.json()["status"] == "completed"
        
        # Update to cancelled
        cancel_response = admin_session.put(f"{BASE_URL}/api/events/bookings/{booking_id}", json={
            "status": "cancelled"
        })
        assert cancel_response.status_code == 200
        assert cancel_response.json()["status"] == "cancelled"
        
        print(f"PASS: Booking status updates work (confirmed -> completed -> cancelled)")
    
    def test_event_bookings_delete(self, admin_session):
        """DELETE /api/events/bookings/{id} deletes a booking"""
        # First create a booking
        test_booking = {
            "property_id": "aldgate-flats",
            "event_name": f"TEST_Delete_{uuid.uuid4().hex[:6]}",
            "date": "2026-02-25"
        }
        create_response = admin_session.post(f"{BASE_URL}/api/events/bookings", json=test_booking)
        booking_id = create_response.json()["id"]
        
        # Delete the booking
        delete_response = admin_session.delete(f"{BASE_URL}/api/events/bookings/{booking_id}")
        assert delete_response.status_code == 200
        
        print(f"PASS: Booking deleted - {booking_id}")
    
    # ==================== CATERING PACKAGES ====================
    
    def test_catering_packages_returns_200(self, admin_session):
        """GET /api/events/catering returns 200"""
        response = admin_session.get(f"{BASE_URL}/api/events/catering")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"PASS: GET /api/events/catering returns 200")
    
    def test_catering_packages_auto_seeded(self, admin_session):
        """GET /api/events/catering returns auto-seeded packages"""
        response = admin_session.get(f"{BASE_URL}/api/events/catering")
        packages = response.json()
        
        assert len(packages) >= 4, f"Expected at least 4 catering packages, got {len(packages)}"
        
        # Check expected packages
        package_names = [p["name"] for p in packages]
        expected_packages = ["Tea & Coffee", "Morning Break", "Working Lunch", "Full Day Package"]
        for expected in expected_packages:
            assert expected in package_names, f"Missing catering package: {expected}"
        
        # Check package structure
        for pkg in packages:
            assert "id" in pkg
            assert "name" in pkg
            assert "price_per_person" in pkg
            assert "items" in pkg
            assert isinstance(pkg["items"], list)
        
        print(f"PASS: Catering packages auto-seeded - {package_names}")
    
    def test_catering_packages_have_prices(self, admin_session):
        """Catering packages have correct price structure"""
        response = admin_session.get(f"{BASE_URL}/api/events/catering")
        packages = response.json()
        
        for pkg in packages:
            assert pkg["price_per_person"] > 0, f"Package {pkg['name']} should have price > 0"
        
        # Check specific prices
        tea_coffee = next((p for p in packages if p["name"] == "Tea & Coffee"), None)
        full_day = next((p for p in packages if p["name"] == "Full Day Package"), None)
        
        if tea_coffee and full_day:
            assert tea_coffee["price_per_person"] < full_day["price_per_person"], \
                "Tea & Coffee should be cheaper than Full Day Package"
        
        print(f"PASS: Catering packages have valid prices")


class TestCleanup:
    """Cleanup test data"""
    
    def test_cleanup_test_items(self, admin_session):
        """Clean up TEST_ prefixed items"""
        # Clean up lost & found items
        lf_response = admin_session.get(f"{BASE_URL}/api/lost-found/all")
        if lf_response.status_code == 200:
            items = lf_response.json()["items"]
            for item in items:
                if item["item_name"].startswith("TEST_"):
                    admin_session.delete(f"{BASE_URL}/api/lost-found/{item['id']}")
        
        # Clean up event rooms
        rooms_response = admin_session.get(f"{BASE_URL}/api/events/rooms/all")
        if rooms_response.status_code == 200:
            rooms = rooms_response.json()
            for room in rooms:
                if room["name"].startswith("TEST_"):
                    admin_session.delete(f"{BASE_URL}/api/events/rooms/{room['id']}")
        
        # Clean up event bookings
        bookings_response = admin_session.get(f"{BASE_URL}/api/events/bookings/all")
        if bookings_response.status_code == 200:
            bookings = bookings_response.json()
            for booking in bookings:
                if booking["event_name"].startswith("TEST_"):
                    admin_session.delete(f"{BASE_URL}/api/events/bookings/{booking['id']}")
        
        print("PASS: Test data cleaned up")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
