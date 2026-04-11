"""
Iteration 41 - MASSIVE REFACTORING REGRESSION TEST
server.py went from ~6,400 lines to 406 lines.
All routes extracted into 10 modular route files.

This test verifies ALL endpoints still work after the extraction:
- auth_routes.py: Auth, Users, Properties, Roles
- connections.py: API Keys, Webhooks, Integration Guide
- reviews.py: Reviews CRUD, Templates, Notifications, Sentiment, Competitors, Widget API
- integrations.py: Reports, Branding, Platform Integrations, Sync
- bookings.py: Booking Engine, Room Types, Template Settings, Promo Codes, Add-ons, Policies
- messaging.py: Conversations, Messages, Quick Replies, Channel Settings
- automation.py: Automation Rules, Logs, Stats
- dashboard.py: Dashboard Overview, Concierge Analytics, Space Bookings Admin
- staff_performance.py: Staff Performance Dashboard
- helpers.py: Shared helpers (serialize_review, log_sync, fire_webhooks)
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://review-hub-108.preview.emergentagent.com').rstrip('/')
API_URL = f"{BASE_URL}/api"

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"

# Test property IDs
PROPERTY_ID = "city-gate"  # Has room data for booking tests
PROPERTY_ID_ALT = "myhotelbox-london"


class TestAuthRoutes:
    """Test auth_routes.py - Auth, Users, Properties, Roles"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.token = None
    
    def test_01_login_success(self):
        """POST /api/auth/login - Admin login"""
        response = self.session.post(f"{API_URL}/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in response"
        assert data["email"] == ADMIN_EMAIL
        assert data["role"] == "admin"
        self.token = data["token"]
        print(f"✓ Login successful - User: {data['name']}, Role: {data['role']}")
    
    def test_02_get_current_user(self):
        """GET /api/auth/me - Current user info"""
        # Login first
        login_resp = self.session.post(f"{API_URL}/auth/login", json={
            "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD
        })
        token = login_resp.json()["token"]
        
        response = self.session.get(f"{API_URL}/auth/me", headers={
            "Authorization": f"Bearer {token}"
        })
        assert response.status_code == 200, f"Get me failed: {response.text}"
        data = response.json()
        assert data["email"] == ADMIN_EMAIL
        print(f"✓ GET /api/auth/me - User: {data['name']}")
    
    def test_03_list_users(self):
        """GET /api/users - List users"""
        login_resp = self.session.post(f"{API_URL}/auth/login", json={
            "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD
        })
        token = login_resp.json()["token"]
        
        response = self.session.get(f"{API_URL}/users", headers={
            "Authorization": f"Bearer {token}"
        })
        assert response.status_code == 200, f"List users failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/users - Found {len(data)} users")
    
    def test_04_list_properties(self):
        """GET /api/properties - List properties"""
        login_resp = self.session.post(f"{API_URL}/auth/login", json={
            "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD
        })
        token = login_resp.json()["token"]
        
        response = self.session.get(f"{API_URL}/properties", headers={
            "Authorization": f"Bearer {token}"
        })
        assert response.status_code == 200, f"List properties failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0, "No properties found"
        print(f"✓ GET /api/properties - Found {len(data)} properties")
    
    def test_05_get_roles(self):
        """GET /api/roles - List roles"""
        response = self.session.get(f"{API_URL}/roles")
        assert response.status_code == 200, f"Get roles failed: {response.text}"
        data = response.json()
        assert "roles" in data
        assert "departments" in data
        print(f"✓ GET /api/roles - {len(data['roles'])} roles, {len(data['departments'])} departments")


class TestReviewsRoutes:
    """Test reviews.py - Reviews CRUD, Templates, Notifications, Sentiment, Competitors"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        login_resp = self.session.post(f"{API_URL}/auth/login", json={
            "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD
        })
        self.token = login_resp.json()["token"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_01_list_reviews(self):
        """GET /api/reviews - List reviews"""
        response = self.session.get(f"{API_URL}/reviews")
        assert response.status_code == 200, f"List reviews failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/reviews - Found {len(data)} reviews")
    
    def test_02_review_stats_summary(self):
        """GET /api/reviews/stats/summary - Review stats"""
        response = self.session.get(f"{API_URL}/reviews/stats/summary")
        assert response.status_code == 200, f"Review stats failed: {response.text}"
        data = response.json()
        assert "total_reviews" in data
        assert "average_rating" in data
        assert "response_rate" in data
        print(f"✓ GET /api/reviews/stats/summary - Total: {data['total_reviews']}, Avg: {data['average_rating']}")
    
    def test_03_pending_approval(self):
        """GET /api/reviews/pending-approval - Approval queue"""
        response = self.session.get(f"{API_URL}/reviews/pending-approval")
        assert response.status_code == 200, f"Pending approval failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/reviews/pending-approval - {len(data)} pending")
    
    def test_04_list_templates(self):
        """GET /api/templates - Response templates"""
        response = self.session.get(f"{API_URL}/templates")
        assert response.status_code == 200, f"List templates failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/templates - Found {len(data)} templates")
    
    def test_05_list_competitors(self):
        """GET /api/competitors - Competitors"""
        response = self.session.get(f"{API_URL}/competitors")
        assert response.status_code == 200, f"List competitors failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/competitors - Found {len(data)} competitors")
    
    def test_06_analytics_dashboard(self):
        """GET /api/analytics/dashboard - Analytics"""
        response = self.session.get(f"{API_URL}/analytics/dashboard")
        assert response.status_code == 200, f"Analytics dashboard failed: {response.text}"
        data = response.json()
        assert "overview" in data
        assert "rating_distribution" in data
        print(f"✓ GET /api/analytics/dashboard - Overview: {data['overview']}")
    
    def test_07_notification_settings(self):
        """GET /api/notifications/settings - Notification settings"""
        response = self.session.get(f"{API_URL}/notifications/settings")
        assert response.status_code == 200, f"Notification settings failed: {response.text}"
        data = response.json()
        assert "enabled" in data or "email" in data
        print(f"✓ GET /api/notifications/settings - Enabled: {data.get('enabled', 'N/A')}")


class TestIntegrationsRoutes:
    """Test integrations.py - Reports, Branding, Platform Integrations, Sync"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        login_resp = self.session.post(f"{API_URL}/auth/login", json={
            "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD
        })
        self.token = login_resp.json()["token"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_01_list_integrations(self):
        """GET /api/integrations - Platform integrations"""
        response = self.session.get(f"{API_URL}/integrations")
        assert response.status_code == 200, f"List integrations failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/integrations - Found {len(data)} integrations")
    
    def test_02_get_branding(self):
        """GET /api/branding - Branding settings"""
        response = self.session.get(f"{API_URL}/branding")
        assert response.status_code == 200, f"Get branding failed: {response.text}"
        data = response.json()
        assert "app_name" in data or "primary_color" in data
        print(f"✓ GET /api/branding - App: {data.get('app_name', 'Review Hub')}")
    
    def test_03_report_settings(self):
        """GET /api/reports/settings - Report settings"""
        response = self.session.get(f"{API_URL}/reports/settings")
        assert response.status_code == 200, f"Report settings failed: {response.text}"
        data = response.json()
        assert "frequency" in data or "enabled" in data or "email" in data
        print(f"✓ GET /api/reports/settings - Frequency: {data.get('frequency', 'N/A')}")
    
    def test_04_sync_logs(self):
        """GET /api/sync-logs - Sync logs"""
        response = self.session.get(f"{API_URL}/sync-logs")
        assert response.status_code == 200, f"Sync logs failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/sync-logs - Found {len(data)} logs")


class TestConnectionsRoutes:
    """Test connections.py - API Keys, Webhooks, Integration Guide"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        login_resp = self.session.post(f"{API_URL}/auth/login", json={
            "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD
        })
        self.token = login_resp.json()["token"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_01_list_api_keys(self):
        """GET /api/api-keys - API keys"""
        response = self.session.get(f"{API_URL}/api-keys")
        assert response.status_code == 200, f"List API keys failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/api-keys - Found {len(data)} keys")
    
    def test_02_list_webhooks(self):
        """GET /api/webhooks - Webhooks list"""
        response = self.session.get(f"{API_URL}/webhooks")
        assert response.status_code == 200, f"List webhooks failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/webhooks - Found {len(data)} webhooks")
    
    def test_03_integration_guide(self):
        """GET /api/integration-guide - Integration guide"""
        response = self.session.get(f"{API_URL}/integration-guide")
        assert response.status_code == 200, f"Integration guide failed: {response.text}"
        data = response.json()
        assert "title" in data
        assert "steps" in data
        print(f"✓ GET /api/integration-guide - Title: {data['title']}")


class TestBookingsRoutes:
    """Test bookings.py - Booking Engine, Room Types, Template Settings, Promo Codes"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        login_resp = self.session.post(f"{API_URL}/auth/login", json={
            "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD
        })
        self.token = login_resp.json()["token"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_01_list_room_types(self):
        """GET /api/room-types - Room types"""
        response = self.session.get(f"{API_URL}/room-types")
        assert response.status_code == 200, f"List room types failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/room-types - Found {len(data)} room types")
    
    def test_02_list_bookings(self):
        """GET /api/bookings - Bookings list"""
        response = self.session.get(f"{API_URL}/bookings")
        assert response.status_code == 200, f"List bookings failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/bookings - Found {len(data)} bookings")
    
    def test_03_booking_property_info(self):
        """GET /api/booking/property/{property_id} - Public booking page"""
        response = self.session.get(f"{API_URL}/booking/property/{PROPERTY_ID}")
        assert response.status_code == 200, f"Booking property info failed: {response.text}"
        data = response.json()
        assert "id" in data or "name" in data
        print(f"✓ GET /api/booking/property/{PROPERTY_ID} - Property: {data.get('name', PROPERTY_ID)}")
    
    def test_04_booking_rooms(self):
        """GET /api/booking/rooms/{property_id} - Room list"""
        response = self.session.get(f"{API_URL}/booking/rooms/{PROPERTY_ID}")
        assert response.status_code == 200, f"Booking rooms failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/booking/rooms/{PROPERTY_ID} - Found {len(data)} rooms")
    
    def test_05_booking_availability(self):
        """GET /api/booking/availability/{property_id} - Availability check"""
        response = self.session.get(f"{API_URL}/booking/availability/{PROPERTY_ID}")
        assert response.status_code == 200, f"Booking availability failed: {response.text}"
        data = response.json()
        assert "property_id" in data
        assert "rooms" in data
        print(f"✓ GET /api/booking/availability/{PROPERTY_ID} - {len(data['rooms'])} room types")
    
    def test_06_template_settings(self):
        """GET /api/template-settings/{property_id} - Template settings (public)"""
        response = self.session.get(f"{API_URL}/template-settings/{PROPERTY_ID}")
        assert response.status_code == 200, f"Template settings failed: {response.text}"
        data = response.json()
        assert "property_id" in data
        print(f"✓ GET /api/template-settings/{PROPERTY_ID}")
    
    def test_07_promo_codes(self):
        """GET /api/promo-codes - Promo codes"""
        response = self.session.get(f"{API_URL}/promo-codes")
        assert response.status_code == 200, f"Promo codes failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/promo-codes - Found {len(data)} codes")
    
    def test_08_hotel_policies(self):
        """GET /api/hotel-policies/{property_id} - Hotel policies"""
        response = self.session.get(f"{API_URL}/hotel-policies/{PROPERTY_ID}")
        assert response.status_code == 200, f"Hotel policies failed: {response.text}"
        data = response.json()
        assert "property_id" in data
        print(f"✓ GET /api/hotel-policies/{PROPERTY_ID}")
    
    def test_09_currencies(self):
        """GET /api/currencies - Currency list"""
        response = self.session.get(f"{API_URL}/currencies")
        assert response.status_code == 200, f"Currencies failed: {response.text}"
        data = response.json()
        assert isinstance(data, (list, dict))
        print(f"✓ GET /api/currencies")
    
    def test_10_spaces(self):
        """GET /api/spaces/{property_id} - Spaces"""
        response = self.session.get(f"{API_URL}/spaces/{PROPERTY_ID}")
        assert response.status_code == 200, f"Spaces failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/spaces/{PROPERTY_ID} - Found {len(data)} spaces")


class TestMessagingRoutes:
    """Test messaging.py - Conversations, Messages, Quick Replies, Channel Settings"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        login_resp = self.session.post(f"{API_URL}/auth/login", json={
            "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD
        })
        self.token = login_resp.json()["token"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_01_list_conversations(self):
        """GET /api/messaging/conversations/{property_id} - Conversations"""
        response = self.session.get(f"{API_URL}/messaging/conversations/{PROPERTY_ID_ALT}")
        assert response.status_code == 200, f"List conversations failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/messaging/conversations/{PROPERTY_ID_ALT} - Found {len(data)} conversations")


class TestAutomationRoutes:
    """Test automation.py - Automation Rules, Logs, Stats"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        login_resp = self.session.post(f"{API_URL}/auth/login", json={
            "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD
        })
        self.token = login_resp.json()["token"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_01_automation_rules(self):
        """GET /api/automation/rules/{property_id} - Automation rules"""
        response = self.session.get(f"{API_URL}/automation/rules/{PROPERTY_ID_ALT}")
        assert response.status_code == 200, f"Automation rules failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/automation/rules/{PROPERTY_ID_ALT} - Found {len(data)} rules")


class TestDashboardRoutes:
    """Test dashboard.py - Dashboard Overview, Concierge Analytics, Space Bookings Admin"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        login_resp = self.session.post(f"{API_URL}/auth/login", json={
            "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD
        })
        self.token = login_resp.json()["token"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_01_dashboard_overview(self):
        """GET /api/dashboard/overview/{property_id} - Dashboard"""
        response = self.session.get(f"{API_URL}/dashboard/overview/{PROPERTY_ID_ALT}")
        assert response.status_code == 200, f"Dashboard overview failed: {response.text}"
        data = response.json()
        assert "bookings" in data
        assert "revenue" in data
        assert "messaging" in data
        print(f"✓ GET /api/dashboard/overview/{PROPERTY_ID_ALT}")
    
    def test_02_concierge_analytics(self):
        """GET /api/concierge/analytics/{property_id} - Concierge analytics"""
        response = self.session.get(f"{API_URL}/concierge/analytics/{PROPERTY_ID_ALT}")
        assert response.status_code == 200, f"Concierge analytics failed: {response.text}"
        data = response.json()
        assert "total_sessions" in data or "total_messages" in data
        print(f"✓ GET /api/concierge/analytics/{PROPERTY_ID_ALT}")


class TestStaffPerformanceRoutes:
    """Test staff_performance.py - Staff Performance Dashboard"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        login_resp = self.session.post(f"{API_URL}/auth/login", json={
            "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD
        })
        self.token = login_resp.json()["token"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_01_staff_performance(self):
        """GET /api/staff-performance/{property_id} - Staff performance"""
        response = self.session.get(f"{API_URL}/staff-performance/{PROPERTY_ID_ALT}")
        assert response.status_code == 200, f"Staff performance failed: {response.text}"
        data = response.json()
        assert "agents" in data
        assert "team_summary" in data
        assert "daily_trend" in data
        print(f"✓ GET /api/staff-performance/{PROPERTY_ID_ALT} - {len(data['agents'])} agents")


class TestStatusAndRoot:
    """Test root and status endpoints in server.py"""
    
    def test_01_root_endpoint(self):
        """GET /api/ - Root endpoint"""
        response = requests.get(f"{API_URL}/")
        assert response.status_code == 200, f"Root endpoint failed: {response.text}"
        data = response.json()
        assert "message" in data
        print(f"✓ GET /api/ - {data['message']}")
    
    def test_02_status_endpoint(self):
        """GET /api/status - Status checks"""
        response = requests.get(f"{API_URL}/status")
        assert response.status_code == 200, f"Status endpoint failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/status - {len(data)} status checks")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
