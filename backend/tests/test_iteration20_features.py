"""
Iteration 20 Backend Tests
Tests for:
- P0: Inbound platform webhooks (POST /api/platforms/{platform}/incoming)
- P1: Property mapping (PUT /api/properties/{id}/mapping, GET /api/properties/by-external/{id})
- Sync logs (GET /api/sync-logs)
"""
import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
API_KEY = "rhk_17354979397db960bcb68db21ed42b7acc103e7940715667"

class TestAuth:
    """Authentication tests"""
    
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


class TestInboundWebhooks:
    """P0: Inbound platform webhook tests"""
    
    @pytest.fixture
    def auth_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        return response.json().get("token")
    
    def test_inbound_webhook_creates_review(self, auth_token):
        """POST /api/platforms/booking.com/incoming with X-Platform-Secret creates review"""
        unique_id = f"TEST_inbound_{uuid.uuid4().hex[:8]}"
        payload = {
            "external_review_id": unique_id,
            "guest_name": "John Smith",
            "rating": 5,
            "review_text": "Excellent stay! The staff was very helpful.",
            "stay_date": "2026-01-10",
            "room_type": "Deluxe Suite",
            "property_id": "default"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/platforms/booking.com/incoming",
            json=payload,
            headers={"X-Platform-Secret": API_KEY}
        )
        
        assert response.status_code == 200, f"Inbound webhook failed: {response.text}"
        data = response.json()
        assert data["status"] == "created"
        assert "review_id" in data
        print(f"✓ Inbound webhook created review: {data['review_id']}")
        
        # Verify review exists
        review_response = requests.get(f"{BASE_URL}/api/reviews/{data['review_id']}")
        assert review_response.status_code == 200
        review = review_response.json()
        assert review["guest_name"] == "John Smith"
        assert review["platform"] == "booking.com"
        assert review["rating"] == 5
        assert review["external_review_id"] == unique_id
        print(f"✓ Review verified in database")
    
    def test_inbound_webhook_duplicate_skipped(self, auth_token):
        """POST /api/platforms/booking.com/incoming with duplicate external_review_id returns skipped"""
        unique_id = f"TEST_dup_{uuid.uuid4().hex[:8]}"
        payload = {
            "external_review_id": unique_id,
            "guest_name": "Jane Doe",
            "rating": 4,
            "review_text": "Great experience!",
            "property_id": "default"
        }
        
        # First request - should create
        response1 = requests.post(
            f"{BASE_URL}/api/platforms/booking.com/incoming",
            json=payload,
            headers={"X-Platform-Secret": API_KEY}
        )
        assert response1.status_code == 200
        assert response1.json()["status"] == "created"
        print(f"✓ First request created review")
        
        # Second request with same external_review_id - should skip
        response2 = requests.post(
            f"{BASE_URL}/api/platforms/booking.com/incoming",
            json=payload,
            headers={"X-Platform-Secret": API_KEY}
        )
        assert response2.status_code == 200
        data = response2.json()
        assert data["status"] == "skipped"
        assert "already exists" in data["message"].lower()
        print(f"✓ Duplicate review correctly skipped")
    
    def test_inbound_batch_endpoint(self, auth_token):
        """POST /api/platforms/google/incoming/batch accepts array of reviews"""
        reviews = [
            {
                "external_review_id": f"TEST_batch1_{uuid.uuid4().hex[:8]}",
                "guest_name": "Batch User 1",
                "rating": 5,
                "review_text": "Amazing place!"
            },
            {
                "external_review_id": f"TEST_batch2_{uuid.uuid4().hex[:8]}",
                "guest_name": "Batch User 2",
                "rating": 4,
                "review_text": "Very good stay"
            }
        ]
        
        response = requests.post(
            f"{BASE_URL}/api/platforms/google/incoming/batch",
            json=reviews,
            headers={"X-Platform-Secret": API_KEY}
        )
        
        assert response.status_code == 200, f"Batch endpoint failed: {response.text}"
        data = response.json()
        assert data["status"] == "success"
        assert data["created"] == 2
        assert data["skipped"] == 0
        print(f"✓ Batch endpoint created {data['created']} reviews")
    
    def test_inbound_url_endpoint(self, auth_token):
        """GET /api/platforms/google/inbound-url returns webhook URL, secret, payload format"""
        response = requests.get(
            f"{BASE_URL}/api/platforms/google/inbound-url",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200, f"Inbound URL endpoint failed: {response.text}"
        data = response.json()
        
        assert "webhook_url" in data
        assert "batch_url" in data
        assert "secret" in data
        assert "headers" in data
        assert "payload_format" in data
        
        assert "/api/platforms/google/incoming" in data["webhook_url"]
        assert data["secret"].startswith("psk_") or data["secret"].startswith("rhk_")
        print(f"✓ Inbound URL endpoint returned correct format")
        print(f"  Webhook URL: {data['webhook_url']}")
        print(f"  Secret: {data['secret'][:12]}...")
    
    def test_inbound_webhook_no_auth_returns_401(self):
        """POST /api/platforms/booking.com/incoming without auth returns 401"""
        payload = {
            "external_review_id": f"TEST_noauth_{uuid.uuid4().hex[:8]}",
            "guest_name": "No Auth User",
            "rating": 3,
            "review_text": "Test without auth"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/platforms/booking.com/incoming",
            json=payload
            # No auth header
        )
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print(f"✓ Unauthenticated request correctly rejected with 401")


class TestSyncLogs:
    """Sync log tests"""
    
    @pytest.fixture
    def auth_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        return response.json().get("token")
    
    def test_get_sync_logs(self, auth_token):
        """GET /api/sync-logs returns sync activity"""
        response = requests.get(
            f"{BASE_URL}/api/sync-logs",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200, f"Sync logs failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        
        if len(data) > 0:
            log = data[0]
            assert "platform" in log
            assert "direction" in log
            assert "status" in log
            assert "timestamp" in log
            print(f"✓ Sync logs returned {len(data)} entries")
            print(f"  Latest: {log['platform']} - {log['direction']} - {log['status']}")
        else:
            print(f"✓ Sync logs endpoint working (no entries yet)")
    
    def test_sync_logs_filter_by_platform(self, auth_token):
        """GET /api/sync-logs?platform=booking.com filters by platform"""
        response = requests.get(
            f"{BASE_URL}/api/sync-logs?platform=booking.com",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # All returned logs should be for booking.com
        for log in data:
            assert log["platform"] == "booking.com", f"Expected booking.com, got {log['platform']}"
        
        print(f"✓ Platform filter working, returned {len(data)} booking.com logs")


class TestPropertyMapping:
    """P1: Property mapping tests"""
    
    @pytest.fixture
    def auth_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        return response.json().get("token")
    
    def test_update_property_mapping(self, auth_token):
        """PUT /api/properties/{id}/mapping saves external_id, external_name, external_system"""
        mapping_data = {
            "external_id": f"test-ext-{uuid.uuid4().hex[:8]}",
            "external_name": "Test External Property",
            "external_system": "myhotelbox"
        }
        
        response = requests.put(
            f"{BASE_URL}/api/properties/default/mapping",
            json=mapping_data,
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200, f"Property mapping failed: {response.text}"
        data = response.json()
        
        assert data["external_id"] == mapping_data["external_id"]
        assert data["external_name"] == mapping_data["external_name"]
        assert data["external_system"] == mapping_data["external_system"]
        print(f"✓ Property mapping saved successfully")
        print(f"  External ID: {data['external_id']}")
        
        return mapping_data["external_id"]
    
    def test_get_property_by_external_id(self, auth_token):
        """GET /api/properties/by-external/{id} looks up property by external ID"""
        # First, set a known external_id
        external_id = f"lookup-test-{uuid.uuid4().hex[:8]}"
        mapping_data = {
            "external_id": external_id,
            "external_name": "Lookup Test Property",
            "external_system": "myhotelbox"
        }
        
        requests.put(
            f"{BASE_URL}/api/properties/default/mapping",
            json=mapping_data,
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        # Now lookup by external_id
        response = requests.get(f"{BASE_URL}/api/properties/by-external/{external_id}")
        
        assert response.status_code == 200, f"Lookup failed: {response.text}"
        data = response.json()
        
        assert data["external_id"] == external_id
        assert data["id"] == "default"
        print(f"✓ Property lookup by external ID successful")
    
    def test_get_property_by_external_id_not_found(self):
        """GET /api/properties/by-external/{id} returns 404 for unknown ID"""
        response = requests.get(f"{BASE_URL}/api/properties/by-external/nonexistent-id-12345")
        
        assert response.status_code == 404
        print(f"✓ Unknown external ID correctly returns 404")


class TestExtractedComponents:
    """Test that extracted components still work"""
    
    @pytest.fixture
    def auth_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        return response.json().get("token")
    
    def test_reviews_endpoint(self, auth_token):
        """GET /api/reviews still works"""
        response = requests.get(
            f"{BASE_URL}/api/reviews",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Reviews endpoint working, returned {len(data)} reviews")
    
    def test_analytics_endpoint(self, auth_token):
        """GET /api/analytics/dashboard still works"""
        response = requests.get(
            f"{BASE_URL}/api/analytics/dashboard",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        # Analytics returns overview with total_reviews inside
        assert "overview" in data
        assert "total_reviews" in data["overview"]
        print(f"✓ Analytics endpoint working, total reviews: {data['overview']['total_reviews']}")
    
    def test_integrations_endpoint(self, auth_token):
        """GET /api/integrations still works"""
        response = requests.get(
            f"{BASE_URL}/api/integrations",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Integrations endpoint working, returned {len(data)} platforms")
    
    def test_branding_endpoint(self, auth_token):
        """GET /api/branding still works"""
        response = requests.get(
            f"{BASE_URL}/api/branding",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "app_name" in data
        print(f"✓ Branding endpoint working")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
