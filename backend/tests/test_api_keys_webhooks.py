"""
Backend API Tests for API Keys and Webhooks endpoints
Tests the new API Connection and Webhooks features
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuth:
    """Authentication tests - prerequisite for other tests"""
    
    @pytest.fixture(scope="class")
    def session(self):
        """Create a session that persists cookies"""
        return requests.Session()
    
    def test_login_admin(self, session):
        """Test admin login with correct credentials"""
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data
        assert data["email"] == "admin@hotelbox.com"
        assert data["role"] == "admin"
        print(f"✓ Admin login successful: {data['name']}")
        return data["token"]


class TestApiKeys:
    """API Keys CRUD tests"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        """Get authenticated session"""
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return session
    
    def test_list_api_keys_requires_auth(self):
        """Test that listing API keys requires authentication"""
        response = requests.get(f"{BASE_URL}/api/api-keys")
        assert response.status_code == 401, "Should require auth"
        print("✓ GET /api/api-keys requires authentication")
    
    def test_list_api_keys(self, auth_session):
        """Test listing API keys with auth"""
        response = auth_session.get(f"{BASE_URL}/api/api-keys")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/api-keys returns list with {len(data)} keys")
    
    def test_create_api_key(self, auth_session):
        """Test creating a new API key"""
        response = auth_session.post(f"{BASE_URL}/api/api-keys", json={
            "label": "TEST_Integration_Key"
        })
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "id" in data
        assert "key" in data
        assert data["label"] == "TEST_Integration_Key"
        assert data["key"].startswith("rhk_")
        assert data["is_active"] == True
        assert "key_masked" in data
        print(f"✓ POST /api/api-keys creates key: {data['key_masked']}")
        return data
    
    def test_create_and_verify_api_key(self, auth_session):
        """Test creating API key and verifying it appears in list"""
        # Create
        create_response = auth_session.post(f"{BASE_URL}/api/api-keys", json={
            "label": "TEST_Verify_Key"
        })
        assert create_response.status_code == 200
        created_key = create_response.json()
        key_id = created_key["id"]
        
        # Verify in list
        list_response = auth_session.get(f"{BASE_URL}/api/api-keys")
        assert list_response.status_code == 200
        keys = list_response.json()
        found = any(k["id"] == key_id for k in keys)
        assert found, "Created key not found in list"
        print(f"✓ Created key {key_id} verified in list")
        
        # Cleanup
        auth_session.delete(f"{BASE_URL}/api/api-keys/{key_id}")
    
    def test_delete_api_key(self, auth_session):
        """Test deleting an API key"""
        # First create a key to delete
        create_response = auth_session.post(f"{BASE_URL}/api/api-keys", json={
            "label": "TEST_Delete_Key"
        })
        assert create_response.status_code == 200
        key_id = create_response.json()["id"]
        
        # Delete it
        delete_response = auth_session.delete(f"{BASE_URL}/api/api-keys/{key_id}")
        assert delete_response.status_code == 200, f"Delete failed: {delete_response.text}"
        
        # Verify it's gone
        list_response = auth_session.get(f"{BASE_URL}/api/api-keys")
        keys = list_response.json()
        found = any(k["id"] == key_id for k in keys)
        assert not found, "Deleted key still in list"
        print(f"✓ DELETE /api/api-keys/{key_id} successful")
    
    def test_delete_nonexistent_key(self, auth_session):
        """Test deleting a non-existent key returns 404"""
        response = auth_session.delete(f"{BASE_URL}/api/api-keys/nonexistent-id-12345")
        assert response.status_code == 404
        print("✓ DELETE non-existent key returns 404")


class TestWebhooks:
    """Webhooks CRUD tests"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        """Get authenticated session"""
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return session
    
    def test_list_webhooks_requires_auth(self):
        """Test that listing webhooks requires authentication"""
        response = requests.get(f"{BASE_URL}/api/webhooks")
        assert response.status_code == 401, "Should require auth"
        print("✓ GET /api/webhooks requires authentication")
    
    def test_list_webhooks(self, auth_session):
        """Test listing webhooks with auth"""
        response = auth_session.get(f"{BASE_URL}/api/webhooks")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/webhooks returns list with {len(data)} webhooks")
    
    def test_get_webhook_events(self, auth_session):
        """Test getting available webhook events"""
        response = auth_session.get(f"{BASE_URL}/api/webhooks/events")
        assert response.status_code == 200, f"Failed: {response.text}"
        events = response.json()
        assert isinstance(events, list)
        assert len(events) > 0
        # Check event structure
        event = events[0]
        assert "id" in event
        assert "name" in event
        assert "description" in event
        print(f"✓ GET /api/webhooks/events returns {len(events)} events")
        for e in events:
            print(f"  - {e['id']}: {e['name']}")
    
    def test_create_webhook(self, auth_session):
        """Test creating a new webhook"""
        response = auth_session.post(f"{BASE_URL}/api/webhooks", json={
            "url": "https://test.example.com/webhook",
            "label": "TEST_Webhook",
            "events": ["review.created", "review.responded"]
        })
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "id" in data
        assert "secret" in data
        assert data["url"] == "https://test.example.com/webhook"
        assert data["label"] == "TEST_Webhook"
        assert data["is_active"] == True
        assert "review.created" in data["events"]
        print(f"✓ POST /api/webhooks creates webhook: {data['id']}")
        return data
    
    def test_create_webhook_requires_url(self, auth_session):
        """Test that creating webhook without URL fails"""
        response = auth_session.post(f"{BASE_URL}/api/webhooks", json={
            "label": "No URL Webhook"
        })
        assert response.status_code == 400, f"Should fail without URL: {response.text}"
        print("✓ POST /api/webhooks without URL returns 400")
    
    def test_create_webhook_invalid_event(self, auth_session):
        """Test that creating webhook with invalid event fails"""
        response = auth_session.post(f"{BASE_URL}/api/webhooks", json={
            "url": "https://test.example.com/webhook",
            "events": ["invalid.event"]
        })
        assert response.status_code == 400, f"Should fail with invalid event: {response.text}"
        print("✓ POST /api/webhooks with invalid event returns 400")
    
    def test_create_and_verify_webhook(self, auth_session):
        """Test creating webhook and verifying it appears in list"""
        # Create
        create_response = auth_session.post(f"{BASE_URL}/api/webhooks", json={
            "url": "https://verify.example.com/webhook",
            "label": "TEST_Verify_Webhook"
        })
        assert create_response.status_code == 200
        created = create_response.json()
        webhook_id = created["id"]
        
        # Verify in list
        list_response = auth_session.get(f"{BASE_URL}/api/webhooks")
        assert list_response.status_code == 200
        webhooks = list_response.json()
        found = any(w["id"] == webhook_id for w in webhooks)
        assert found, "Created webhook not found in list"
        print(f"✓ Created webhook {webhook_id} verified in list")
        
        # Cleanup
        auth_session.delete(f"{BASE_URL}/api/webhooks/{webhook_id}")
    
    def test_update_webhook(self, auth_session):
        """Test updating a webhook"""
        # Create first
        create_response = auth_session.post(f"{BASE_URL}/api/webhooks", json={
            "url": "https://update.example.com/webhook",
            "label": "TEST_Update_Webhook"
        })
        assert create_response.status_code == 200
        webhook_id = create_response.json()["id"]
        
        # Update
        update_response = auth_session.put(f"{BASE_URL}/api/webhooks/{webhook_id}", json={
            "label": "TEST_Updated_Label",
            "is_active": False
        })
        assert update_response.status_code == 200, f"Update failed: {update_response.text}"
        updated = update_response.json()
        assert updated["label"] == "TEST_Updated_Label"
        assert updated["is_active"] == False
        print(f"✓ PUT /api/webhooks/{webhook_id} updates webhook")
        
        # Cleanup
        auth_session.delete(f"{BASE_URL}/api/webhooks/{webhook_id}")
    
    def test_delete_webhook(self, auth_session):
        """Test deleting a webhook"""
        # Create first
        create_response = auth_session.post(f"{BASE_URL}/api/webhooks", json={
            "url": "https://delete.example.com/webhook",
            "label": "TEST_Delete_Webhook"
        })
        assert create_response.status_code == 200
        webhook_id = create_response.json()["id"]
        
        # Delete
        delete_response = auth_session.delete(f"{BASE_URL}/api/webhooks/{webhook_id}")
        assert delete_response.status_code == 200, f"Delete failed: {delete_response.text}"
        
        # Verify gone
        list_response = auth_session.get(f"{BASE_URL}/api/webhooks")
        webhooks = list_response.json()
        found = any(w["id"] == webhook_id for w in webhooks)
        assert not found, "Deleted webhook still in list"
        print(f"✓ DELETE /api/webhooks/{webhook_id} successful")
    
    def test_delete_nonexistent_webhook(self, auth_session):
        """Test deleting a non-existent webhook returns 404"""
        response = auth_session.delete(f"{BASE_URL}/api/webhooks/nonexistent-id-12345")
        assert response.status_code == 404
        print("✓ DELETE non-existent webhook returns 404")


class TestDashboardStats:
    """Test dashboard stats endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        """Get authenticated session"""
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200
        return session
    
    def test_reviews_stats_summary(self, auth_session):
        """Test reviews stats summary endpoint"""
        response = auth_session.get(f"{BASE_URL}/api/reviews/stats/summary")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "total_reviews" in data
        assert "average_rating" in data
        assert "response_rate" in data
        assert "pending" in data
        print(f"✓ GET /api/reviews/stats/summary: {data['total_reviews']} reviews, {data['average_rating']}/5 avg, {data['response_rate']}% response rate")
    
    def test_reviews_list(self, auth_session):
        """Test reviews list endpoint"""
        response = auth_session.get(f"{BASE_URL}/api/reviews")
        assert response.status_code == 200, f"Failed: {response.text}"
        reviews = response.json()
        assert isinstance(reviews, list)
        print(f"✓ GET /api/reviews returns {len(reviews)} reviews")


class TestCleanup:
    """Cleanup test data"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        """Get authenticated session"""
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200
        return session
    
    def test_cleanup_test_api_keys(self, auth_session):
        """Clean up any TEST_ prefixed API keys"""
        response = auth_session.get(f"{BASE_URL}/api/api-keys")
        if response.status_code == 200:
            keys = response.json()
            for key in keys:
                if key.get("label", "").startswith("TEST_"):
                    auth_session.delete(f"{BASE_URL}/api/api-keys/{key['id']}")
                    print(f"  Cleaned up API key: {key['label']}")
        print("✓ Cleanup complete for API keys")
    
    def test_cleanup_test_webhooks(self, auth_session):
        """Clean up any TEST_ prefixed webhooks"""
        response = auth_session.get(f"{BASE_URL}/api/webhooks")
        if response.status_code == 200:
            webhooks = response.json()
            for wh in webhooks:
                if wh.get("label", "").startswith("TEST_"):
                    auth_session.delete(f"{BASE_URL}/api/webhooks/{wh['id']}")
                    print(f"  Cleaned up webhook: {wh['label']}")
        print("✓ Cleanup complete for webhooks")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
