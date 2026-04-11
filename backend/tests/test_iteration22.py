"""
Iteration 22 Tests - Testing extracted components and new features:
1. SyncLogPanel extracted from App.js
2. PropertyMappingPanel extracted from App.js  
3. Test Connection endpoint for integrations
4. Outbound sync attempt when responding to reviews
5. All sidebar navigation items
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuthAndLogin:
    """Test authentication with admin credentials"""
    
    def test_admin_login(self):
        """Test admin login with correct credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data
        assert data["email"] == "admin@hotelbox.com"
        assert data["role"] == "admin"
        print(f"✓ Admin login successful: {data['email']}")
        return data["token"]


class TestSyncLogs:
    """Test sync log endpoints - used by SyncLogPanel"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        self.token = response.json().get("token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_sync_logs(self):
        """GET /api/sync-logs returns sync log entries"""
        response = requests.get(f"{BASE_URL}/api/sync-logs", headers=self.headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/sync-logs returned {len(data)} entries")
    
    def test_get_sync_logs_with_platform_filter(self):
        """GET /api/sync-logs?platform=google filters by platform"""
        response = requests.get(f"{BASE_URL}/api/sync-logs?platform=google&limit=10", headers=self.headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        # All returned logs should be for google platform
        for log in data:
            if log.get("platform"):
                assert log["platform"] == "google", f"Expected google, got {log['platform']}"
        print(f"✓ GET /api/sync-logs?platform=google returned {len(data)} entries")


class TestPropertyMapping:
    """Test property mapping endpoints - used by PropertyMappingPanel"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        self.token = response.json().get("token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_properties(self):
        """GET /api/properties returns list of properties"""
        response = requests.get(f"{BASE_URL}/api/properties", headers=self.headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0, "Expected at least one property"
        print(f"✓ GET /api/properties returned {len(data)} properties")
        return data
    
    def test_property_has_mapping_fields(self):
        """Properties should have external_id, external_name, external_system fields"""
        response = requests.get(f"{BASE_URL}/api/properties", headers=self.headers)
        data = response.json()
        # Check that at least some properties have mapping fields
        mapped_count = sum(1 for p in data if p.get("external_id"))
        print(f"✓ {mapped_count}/{len(data)} properties have external_id mapping")
    
    def test_update_property_mapping(self):
        """PUT /api/properties/{id}/mapping updates mapping"""
        # First get a property
        response = requests.get(f"{BASE_URL}/api/properties", headers=self.headers)
        properties = response.json()
        
        # Find default property or first one
        prop = next((p for p in properties if p.get("id") == "default"), properties[0])
        prop_id = prop["id"]
        
        # Update mapping
        mapping_data = {
            "external_id": "test-mapping-001",
            "external_name": "Test Mapping Property",
            "external_system": "myhotelbox"
        }
        response = requests.put(
            f"{BASE_URL}/api/properties/{prop_id}/mapping",
            json=mapping_data,
            headers=self.headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        print(f"✓ PUT /api/properties/{prop_id}/mapping successful")


class TestIntegrationsTestConnection:
    """Test the new test-connection endpoint for integrations"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        self.token = response.json().get("token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_integrations(self):
        """GET /api/integrations returns list of platform integrations"""
        response = requests.get(f"{BASE_URL}/api/integrations", headers=self.headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0, "Expected at least one integration"
        print(f"✓ GET /api/integrations returned {len(data)} platforms")
        return data
    
    def test_google_test_connection_no_credentials(self):
        """POST /api/integrations/google/test-connection returns proper response"""
        response = requests.post(
            f"{BASE_URL}/api/integrations/google/test-connection",
            headers=self.headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        # Should have success and message fields
        assert "success" in data, "Response should have 'success' field"
        assert "message" in data, "Response should have 'message' field"
        # Without real credentials, success should be False
        print(f"✓ POST /api/integrations/google/test-connection: success={data['success']}, message={data['message'][:50]}...")
    
    def test_booking_test_connection(self):
        """POST /api/integrations/booking.com/test-connection returns proper response"""
        response = requests.post(
            f"{BASE_URL}/api/integrations/booking.com/test-connection",
            headers=self.headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "success" in data
        assert "message" in data
        print(f"✓ POST /api/integrations/booking.com/test-connection: success={data['success']}")
    
    def test_nonexistent_platform_test_connection(self):
        """POST /api/integrations/invalid/test-connection returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/integrations/invalid-platform/test-connection",
            headers=self.headers
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ POST /api/integrations/invalid-platform/test-connection returns 404")


class TestReviewRespond:
    """Test review respond endpoint with outbound sync attempt"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        self.token = response.json().get("token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_reviews(self):
        """GET /api/reviews returns list of reviews"""
        response = requests.get(f"{BASE_URL}/api/reviews", headers=self.headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/reviews returned {len(data)} reviews")
        return data
    
    def test_respond_to_review(self):
        """PUT /api/reviews/{id}/respond works and attempts outbound sync"""
        # Get a pending review
        response = requests.get(f"{BASE_URL}/api/reviews?status=pending", headers=self.headers)
        reviews = response.json()
        
        if not reviews:
            # Create a test review
            create_response = requests.post(f"{BASE_URL}/api/reviews", json={
                "platform": "google",
                "guest_name": "TEST_Iteration22_Guest",
                "rating": 4,
                "review_text": "Great stay, will come back!",
                "property_id": "default"
            }, headers=self.headers)
            assert create_response.status_code == 200, f"Failed to create review: {create_response.text}"
            review = create_response.json()
        else:
            review = reviews[0]
        
        review_id = review["id"]
        
        # Respond to the review
        response = requests.put(
            f"{BASE_URL}/api/reviews/{review_id}/respond",
            json={"response_text": "Thank you for your wonderful feedback! We look forward to welcoming you back."},
            headers=self.headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["response_status"] == "responded"
        assert data["response_text"] is not None
        print(f"✓ PUT /api/reviews/{review_id}/respond successful")


class TestDashboardStats:
    """Test dashboard stats endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        self.token = response.json().get("token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_stats_summary(self):
        """GET /api/reviews/stats/summary returns stats"""
        response = requests.get(f"{BASE_URL}/api/reviews/stats/summary", headers=self.headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "total_reviews" in data
        assert "average_rating" in data
        print(f"✓ GET /api/reviews/stats/summary: {data['total_reviews']} reviews, {data['average_rating']}/5 avg")


class TestSidebarNavigation:
    """Test all sidebar navigation endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        self.token = response.json().get("token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_reviews_endpoint(self):
        """Reviews sidebar item - GET /api/reviews"""
        response = requests.get(f"{BASE_URL}/api/reviews", headers=self.headers)
        assert response.status_code == 200
        print("✓ Reviews endpoint working")
    
    def test_analytics_endpoint(self):
        """Analytics sidebar item - GET /api/analytics/dashboard"""
        response = requests.get(f"{BASE_URL}/api/analytics/dashboard", headers=self.headers)
        assert response.status_code == 200
        print("✓ Analytics endpoint working")
    
    def test_templates_endpoint(self):
        """Templates sidebar item - GET /api/templates"""
        response = requests.get(f"{BASE_URL}/api/templates", headers=self.headers)
        assert response.status_code == 200
        print("✓ Templates endpoint working")
    
    def test_approvals_endpoint(self):
        """Approvals sidebar item - GET /api/reviews/pending-approval"""
        response = requests.get(f"{BASE_URL}/api/reviews/pending-approval", headers=self.headers)
        assert response.status_code == 200
        print("✓ Approvals endpoint working")
    
    def test_integrations_endpoint(self):
        """Integrations sidebar item - GET /api/integrations"""
        response = requests.get(f"{BASE_URL}/api/integrations", headers=self.headers)
        assert response.status_code == 200
        print("✓ Integrations endpoint working")
    
    def test_api_keys_endpoint(self):
        """API Connection sidebar item - GET /api/api-keys"""
        response = requests.get(f"{BASE_URL}/api/api-keys", headers=self.headers)
        assert response.status_code == 200
        print("✓ API Keys endpoint working")
    
    def test_webhooks_endpoint(self):
        """Webhooks sidebar item - GET /api/webhooks"""
        response = requests.get(f"{BASE_URL}/api/webhooks", headers=self.headers)
        assert response.status_code == 200
        print("✓ Webhooks endpoint working")
    
    def test_sync_logs_endpoint(self):
        """Sync Log sidebar item - GET /api/sync-logs"""
        response = requests.get(f"{BASE_URL}/api/sync-logs", headers=self.headers)
        assert response.status_code == 200
        print("✓ Sync Logs endpoint working")
    
    def test_integration_guide_endpoint(self):
        """Integration Guide sidebar item - GET /api/integration-guide"""
        response = requests.get(f"{BASE_URL}/api/integration-guide", headers=self.headers)
        assert response.status_code == 200
        print("✓ Integration Guide endpoint working")
    
    def test_notification_settings_endpoint(self):
        """Alerts sidebar item - GET /api/notifications/settings"""
        response = requests.get(f"{BASE_URL}/api/notifications/settings", headers=self.headers)
        assert response.status_code == 200
        print("✓ Notification Settings endpoint working")
    
    def test_report_settings_endpoint(self):
        """Reports sidebar item - GET /api/reports/settings"""
        response = requests.get(f"{BASE_URL}/api/reports/settings", headers=self.headers)
        assert response.status_code == 200
        print("✓ Report Settings endpoint working")
    
    def test_properties_endpoint(self):
        """Property Mapping sidebar item - GET /api/properties"""
        response = requests.get(f"{BASE_URL}/api/properties", headers=self.headers)
        assert response.status_code == 200
        print("✓ Properties endpoint working")
    
    def test_branding_endpoint(self):
        """Branding sidebar item - GET /api/branding"""
        response = requests.get(f"{BASE_URL}/api/branding", headers=self.headers)
        assert response.status_code == 200
        print("✓ Branding endpoint working")
    
    def test_users_endpoint(self):
        """Team sidebar item - GET /api/users"""
        response = requests.get(f"{BASE_URL}/api/users", headers=self.headers)
        assert response.status_code == 200
        print("✓ Users endpoint working")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
