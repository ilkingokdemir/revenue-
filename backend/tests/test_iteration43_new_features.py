"""
Iteration 43 - Testing Four New Competitive Features:
1. Housekeeping Management (room status board, tasks, maintenance)
2. Guest Profiles/CRM (unified guest history from bookings)
3. Campaign Manager (bulk messaging with segmentation)
4. Guest App/Digital Directory (WiFi, services, recommendations)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
PROPERTY_ID = "city-gate"


class TestAuth:
    """Authentication tests"""
    
    def test_admin_login(self):
        """Test admin login returns token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in response"
        assert len(data["token"]) > 0, "Token is empty"
        print(f"✓ Admin login successful, token received")


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for all tests"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Authentication failed - skipping authenticated tests")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}"}


# ==================== HOUSEKEEPING TESTS ====================

class TestHousekeeping:
    """Housekeeping Management endpoint tests"""
    
    def test_seed_room_statuses(self, auth_headers):
        """POST /api/housekeeping/rooms/seed/{property_id} - seed room statuses"""
        response = requests.post(
            f"{BASE_URL}/api/housekeeping/rooms/seed/{PROPERTY_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Seed failed: {response.text}"
        data = response.json()
        assert "message" in data
        assert "count" in data
        print(f"✓ Room seed: {data['message']}, count: {data['count']}")
    
    def test_get_room_statuses(self, auth_headers):
        """GET /api/housekeeping/rooms/{property_id} - list room statuses"""
        response = requests.get(
            f"{BASE_URL}/api/housekeeping/rooms/{PROPERTY_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Get rooms failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ Got {len(data)} room statuses")
    
    def test_get_room_stats(self, auth_headers):
        """GET /api/housekeeping/rooms/{property_id}/stats - room status stats"""
        response = requests.get(
            f"{BASE_URL}/api/housekeeping/rooms/{PROPERTY_ID}/stats",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Get stats failed: {response.text}"
        data = response.json()
        assert "total" in data
        assert "clean" in data
        assert "dirty" in data
        print(f"✓ Room stats: total={data['total']}, clean={data['clean']}, dirty={data['dirty']}")
    
    def test_update_room_status(self, auth_headers):
        """PUT /api/housekeeping/rooms/{room_id}/status - update room status"""
        # First get a room
        rooms_response = requests.get(
            f"{BASE_URL}/api/housekeeping/rooms/{PROPERTY_ID}",
            headers=auth_headers
        )
        rooms = rooms_response.json()
        if not rooms:
            pytest.skip("No rooms to update")
        
        room_id = rooms[0]["id"]
        response = requests.put(
            f"{BASE_URL}/api/housekeeping/rooms/{room_id}/status",
            headers=auth_headers,
            json={"status": "inspected"}
        )
        assert response.status_code == 200, f"Update failed: {response.text}"
        data = response.json()
        assert data["status"] == "inspected"
        print(f"✓ Updated room {room_id} status to 'inspected'")
    
    def test_create_task(self, auth_headers):
        """POST /api/housekeeping/tasks - create task"""
        response = requests.post(
            f"{BASE_URL}/api/housekeeping/tasks",
            headers=auth_headers,
            json={
                "property_id": PROPERTY_ID,
                "room_number": "TEST_101",
                "task_type": "cleaning",
                "priority": "high",
                "status": "pending"
            }
        )
        assert response.status_code == 200, f"Create task failed: {response.text}"
        data = response.json()
        assert data["room_number"] == "TEST_101"
        assert data["task_type"] == "cleaning"
        assert "id" in data
        print(f"✓ Created task: {data['id']}")
        return data["id"]
    
    def test_get_tasks(self, auth_headers):
        """GET /api/housekeeping/tasks/{property_id} - list tasks"""
        response = requests.get(
            f"{BASE_URL}/api/housekeeping/tasks/{PROPERTY_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Get tasks failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Got {len(data)} tasks")
    
    def test_create_maintenance(self, auth_headers):
        """POST /api/housekeeping/maintenance - create maintenance request"""
        response = requests.post(
            f"{BASE_URL}/api/housekeeping/maintenance",
            headers=auth_headers,
            json={
                "property_id": PROPERTY_ID,
                "room_number": "TEST_102",
                "category": "plumbing",
                "description": "TEST_Leaky faucet in bathroom",
                "priority": "normal"
            }
        )
        assert response.status_code == 200, f"Create maintenance failed: {response.text}"
        data = response.json()
        assert data["room_number"] == "TEST_102"
        assert data["category"] == "plumbing"
        assert "id" in data
        print(f"✓ Created maintenance request: {data['id']}")
    
    def test_get_maintenance(self, auth_headers):
        """GET /api/housekeeping/maintenance/{property_id} - list maintenance"""
        response = requests.get(
            f"{BASE_URL}/api/housekeeping/maintenance/{PROPERTY_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Get maintenance failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Got {len(data)} maintenance requests")


# ==================== GUEST PROFILES TESTS ====================

class TestGuestProfiles:
    """Guest Profiles/CRM endpoint tests"""
    
    def test_sync_profiles_from_bookings(self, auth_headers):
        """POST /api/guests/profiles/sync/{property_id} - sync profiles from bookings"""
        response = requests.post(
            f"{BASE_URL}/api/guests/profiles/sync/all",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Sync failed: {response.text}"
        data = response.json()
        assert "message" in data
        assert "created" in data
        assert "updated" in data
        print(f"✓ Sync profiles: {data['message']}")
    
    def test_list_guest_profiles(self, auth_headers):
        """GET /api/guests/profiles/{property_id} - list guest profiles"""
        response = requests.get(
            f"{BASE_URL}/api/guests/profiles/all?sort_by=last_stay",
            headers=auth_headers
        )
        assert response.status_code == 200, f"List profiles failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Got {len(data)} guest profiles")
        return data
    
    def test_get_profile_detail(self, auth_headers):
        """GET /api/guests/profiles/detail/{guest_id} - guest detail with bookings/reviews"""
        # First get a profile
        profiles_response = requests.get(
            f"{BASE_URL}/api/guests/profiles/all",
            headers=auth_headers
        )
        profiles = profiles_response.json()
        if not profiles:
            pytest.skip("No profiles to view")
        
        guest_id = profiles[0]["id"]
        response = requests.get(
            f"{BASE_URL}/api/guests/profiles/detail/{guest_id}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Get detail failed: {response.text}"
        data = response.json()
        assert "name" in data
        assert "bookings" in data
        assert "reviews" in data
        assert "conversations" in data
        print(f"✓ Got profile detail for: {data['name']}, bookings: {len(data['bookings'])}")
    
    def test_update_profile_toggle_vip(self, auth_headers):
        """PUT /api/guests/profiles/{guest_id} - update profile (toggle VIP)"""
        # First get a profile
        profiles_response = requests.get(
            f"{BASE_URL}/api/guests/profiles/all",
            headers=auth_headers
        )
        profiles = profiles_response.json()
        if not profiles:
            pytest.skip("No profiles to update")
        
        guest_id = profiles[0]["id"]
        current_vip = profiles[0].get("vip", False)
        
        response = requests.put(
            f"{BASE_URL}/api/guests/profiles/{guest_id}",
            headers=auth_headers,
            json={"vip": not current_vip}
        )
        assert response.status_code == 200, f"Update failed: {response.text}"
        data = response.json()
        assert data["vip"] == (not current_vip)
        print(f"✓ Toggled VIP status for {guest_id}: {current_vip} -> {not current_vip}")
    
    def test_profile_stats(self, auth_headers):
        """GET /api/guests/profiles/{property_id}/stats - profile stats"""
        response = requests.get(
            f"{BASE_URL}/api/guests/profiles/all/stats",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Get stats failed: {response.text}"
        data = response.json()
        assert "total" in data
        assert "vip" in data
        assert "tiers" in data
        print(f"✓ Profile stats: total={data['total']}, vip={data['vip']}")


# ==================== CAMPAIGNS TESTS ====================

class TestCampaigns:
    """Campaign Manager endpoint tests"""
    
    created_campaign_id = None
    
    def test_create_campaign(self, auth_headers):
        """POST /api/campaigns - create campaign"""
        response = requests.post(
            f"{BASE_URL}/api/campaigns",
            headers=auth_headers,
            json={
                "property_id": PROPERTY_ID,
                "name": "TEST_Welcome Campaign",
                "channel": "email",
                "subject": "Welcome to our hotel!",
                "message": "Dear {guest_name}, thank you for staying with us!",
                "segment": {"has_email": True}
            }
        )
        assert response.status_code == 200, f"Create campaign failed: {response.text}"
        data = response.json()
        assert data["name"] == "TEST_Welcome Campaign"
        assert data["channel"] == "email"
        assert data["status"] == "draft"
        assert "id" in data
        TestCampaigns.created_campaign_id = data["id"]
        print(f"✓ Created campaign: {data['id']}")
    
    def test_list_campaigns(self, auth_headers):
        """GET /api/campaigns/{property_id} - list campaigns"""
        response = requests.get(
            f"{BASE_URL}/api/campaigns/{PROPERTY_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"List campaigns failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Got {len(data)} campaigns")
    
    def test_preview_recipients(self, auth_headers):
        """POST /api/campaigns/{campaign_id}/preview - preview recipients"""
        if not TestCampaigns.created_campaign_id:
            pytest.skip("No campaign created")
        
        response = requests.post(
            f"{BASE_URL}/api/campaigns/{TestCampaigns.created_campaign_id}/preview",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Preview failed: {response.text}"
        data = response.json()
        assert "total" in data
        assert "preview" in data
        print(f"✓ Preview recipients: {data['total']} total")
    
    def test_send_campaign(self, auth_headers):
        """POST /api/campaigns/{campaign_id}/send - send campaign (MOCKED for WhatsApp/SMS)"""
        if not TestCampaigns.created_campaign_id:
            pytest.skip("No campaign created")
        
        response = requests.post(
            f"{BASE_URL}/api/campaigns/{TestCampaigns.created_campaign_id}/send",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Send failed: {response.text}"
        data = response.json()
        assert "message" in data
        assert "sent" in data
        print(f"✓ Campaign send: {data['message']}")
    
    def test_campaign_stats(self, auth_headers):
        """GET /api/campaigns/{property_id}/stats - campaign stats"""
        response = requests.get(
            f"{BASE_URL}/api/campaigns/{PROPERTY_ID}/stats",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Get stats failed: {response.text}"
        data = response.json()
        assert "total" in data
        assert "sent" in data
        assert "draft" in data
        print(f"✓ Campaign stats: total={data['total']}, sent={data['sent']}")
    
    def test_segment_options(self, auth_headers):
        """GET /api/campaigns/segments/options - segmentation filters"""
        response = requests.get(
            f"{BASE_URL}/api/campaigns/segments/options",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Get segments failed: {response.text}"
        data = response.json()
        assert "filters" in data
        assert len(data["filters"]) > 0
        print(f"✓ Got {len(data['filters'])} segment filter options")


# ==================== GUEST APP TESTS ====================

class TestGuestApp:
    """Guest App / Digital Directory endpoint tests"""
    
    def test_get_directory_admin(self, auth_headers):
        """GET /api/guest-app/directory/{property_id} - admin get directory"""
        response = requests.get(
            f"{BASE_URL}/api/guest-app/directory/{PROPERTY_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Get directory failed: {response.text}"
        data = response.json()
        assert "property_id" in data
        assert "services" in data
        assert "local_recommendations" in data
        print(f"✓ Got directory: {len(data.get('services', []))} services, {len(data.get('local_recommendations', []))} recommendations")
    
    def test_update_directory(self, auth_headers):
        """PUT /api/guest-app/directory/{property_id} - update directory"""
        response = requests.put(
            f"{BASE_URL}/api/guest-app/directory/{PROPERTY_ID}",
            headers=auth_headers,
            json={
                "wifi_name": "CityGate_Guest",
                "wifi_password": "Welcome2026",
                "welcome_message": "Welcome to City Gate Hotel! We're delighted to have you.",
                "checkin_time": "15:00",
                "checkout_time": "11:00"
            }
        )
        assert response.status_code == 200, f"Update directory failed: {response.text}"
        data = response.json()
        assert data["wifi_name"] == "CityGate_Guest"
        assert data["wifi_password"] == "Welcome2026"
        print(f"✓ Updated directory: WiFi={data['wifi_name']}")
    
    def test_public_guest_app_no_auth(self):
        """GET /api/guest-app/public/{property_id} - public guest app (no auth)"""
        # This endpoint should work WITHOUT authentication
        response = requests.get(f"{BASE_URL}/api/guest-app/public/{PROPERTY_ID}")
        assert response.status_code == 200, f"Public endpoint failed: {response.text}"
        data = response.json()
        assert "hotel_name" in data
        assert "branding" in data
        assert "directory" in data
        print(f"✓ Public guest app: hotel_name={data['hotel_name']}")
    
    def test_public_guest_app_returns_services(self):
        """Verify public guest app returns services and recommendations"""
        response = requests.get(f"{BASE_URL}/api/guest-app/public/{PROPERTY_ID}")
        assert response.status_code == 200
        data = response.json()
        directory = data.get("directory", {})
        services = directory.get("services", [])
        recommendations = directory.get("local_recommendations", [])
        assert len(services) > 0, "Should have services"
        assert len(recommendations) > 0, "Should have recommendations"
        print(f"✓ Public app has {len(services)} services, {len(recommendations)} recommendations")


# ==================== REGRESSION TESTS ====================

class TestRegression:
    """Regression tests for existing features"""
    
    def test_dashboard_overview(self, auth_headers):
        """GET /api/dashboard/overview/{property_id} - still works"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/overview/{PROPERTY_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Dashboard failed: {response.text}"
        print("✓ Dashboard overview still works")
    
    def test_reviews_list(self, auth_headers):
        """GET /api/reviews - still works"""
        response = requests.get(
            f"{BASE_URL}/api/reviews",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Reviews failed: {response.text}"
        print("✓ Reviews list still works")
    
    def test_bookings_list(self, auth_headers):
        """GET /api/bookings - still works"""
        response = requests.get(
            f"{BASE_URL}/api/bookings",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Bookings failed: {response.text}"
        print("✓ Bookings list still works")
    
    def test_properties_list(self, auth_headers):
        """GET /api/properties - still works"""
        response = requests.get(
            f"{BASE_URL}/api/properties",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Properties failed: {response.text}"
        print("✓ Properties list still works")


# ==================== AUTH REQUIREMENT TESTS ====================

class TestAuthRequirements:
    """Verify endpoints require authentication"""
    
    def test_housekeeping_requires_auth(self):
        """Housekeeping endpoints require auth"""
        response = requests.get(f"{BASE_URL}/api/housekeeping/rooms/{PROPERTY_ID}")
        assert response.status_code == 401, "Should require auth"
        print("✓ Housekeeping requires auth")
    
    def test_guest_profiles_requires_auth(self):
        """Guest profiles endpoints require auth"""
        response = requests.get(f"{BASE_URL}/api/guests/profiles/all")
        assert response.status_code == 401, "Should require auth"
        print("✓ Guest profiles requires auth")
    
    def test_campaigns_requires_auth(self):
        """Campaigns endpoints require auth"""
        response = requests.get(f"{BASE_URL}/api/campaigns/{PROPERTY_ID}")
        assert response.status_code == 401, "Should require auth"
        print("✓ Campaigns requires auth")
    
    def test_guest_app_admin_requires_auth(self):
        """Guest app admin endpoint requires auth"""
        response = requests.get(f"{BASE_URL}/api/guest-app/directory/{PROPERTY_ID}")
        assert response.status_code == 401, "Should require auth"
        print("✓ Guest app admin requires auth")
    
    def test_guest_app_public_no_auth(self):
        """Guest app public endpoint does NOT require auth"""
        response = requests.get(f"{BASE_URL}/api/guest-app/public/{PROPERTY_ID}")
        assert response.status_code == 200, "Public endpoint should work without auth"
        print("✓ Guest app public works without auth")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
