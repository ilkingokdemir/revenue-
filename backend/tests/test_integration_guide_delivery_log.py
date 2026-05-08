"""
Test suite for new features in iteration 15:
1. Webhook Delivery Log (GET /api/webhooks/{id}/deliveries)
2. Integration Guide endpoint (GET /api/integration-guide)
3. Test webhook creates delivery log entry (POST /api/webhooks/{id}/test)
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
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in response"
        return data["token"]
    
    def test_login_success(self, auth_token):
        """Test admin login returns token"""
        assert auth_token is not None
        assert len(auth_token) > 0
        print(f"✓ Login successful, token received")


class TestIntegrationGuide:
    """Integration Guide endpoint tests"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = response.json().get("token")
        return {"Authorization": f"Bearer {token}"}
    
    def test_integration_guide_returns_200(self, auth_headers):
        """GET /api/integration-guide returns 200"""
        response = requests.get(f"{BASE_URL}/api/integration-guide", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ Integration guide endpoint returns 200")
    
    def test_integration_guide_has_title(self, auth_headers):
        """Integration guide has title"""
        response = requests.get(f"{BASE_URL}/api/integration-guide", headers=auth_headers)
        data = response.json()
        assert "title" in data, "Missing title"
        assert "MyHotelBox" in data["title"], f"Title should mention MyHotelBox: {data['title']}"
        print(f"✓ Integration guide title: {data['title']}")
    
    def test_integration_guide_has_base_url(self, auth_headers):
        """Integration guide has base_url"""
        response = requests.get(f"{BASE_URL}/api/integration-guide", headers=auth_headers)
        data = response.json()
        assert "base_url" in data, "Missing base_url"
        assert "/api" in data["base_url"], f"base_url should contain /api: {data['base_url']}"
        print(f"✓ Integration guide base_url: {data['base_url']}")
    
    def test_integration_guide_has_5_steps(self, auth_headers):
        """Integration guide has 5 steps"""
        response = requests.get(f"{BASE_URL}/api/integration-guide", headers=auth_headers)
        data = response.json()
        assert "steps" in data, "Missing steps"
        assert len(data["steps"]) == 5, f"Expected 5 steps, got {len(data['steps'])}"
        for step in data["steps"]:
            assert "step" in step, "Step missing step number"
            assert "title" in step, "Step missing title"
            assert "description" in step, "Step missing description"
        print(f"✓ Integration guide has 5 steps")
    
    def test_integration_guide_has_api_endpoints(self, auth_headers):
        """Integration guide has API endpoints table"""
        response = requests.get(f"{BASE_URL}/api/integration-guide", headers=auth_headers)
        data = response.json()
        assert "api_examples" in data, "Missing api_examples"
        assert "endpoints" in data["api_examples"], "Missing endpoints"
        endpoints = data["api_examples"]["endpoints"]
        assert len(endpoints) >= 5, f"Expected at least 5 endpoints, got {len(endpoints)}"
        for ep in endpoints:
            assert "method" in ep, "Endpoint missing method"
            assert "path" in ep, "Endpoint missing path"
            assert "description" in ep, "Endpoint missing description"
        print(f"✓ Integration guide has {len(endpoints)} API endpoints")
    
    def test_integration_guide_has_webhook_payload_example(self, auth_headers):
        """Integration guide has webhook payload example"""
        response = requests.get(f"{BASE_URL}/api/integration-guide", headers=auth_headers)
        data = response.json()
        assert "webhook_payload_example" in data, "Missing webhook_payload_example"
        payload = data["webhook_payload_example"]
        assert "event" in payload, "Payload missing event"
        assert "data" in payload, "Payload missing data"
        assert payload["event"] == "review.created", f"Expected review.created event, got {payload['event']}"
        print(f"✓ Integration guide has webhook payload example")
    
    def test_integration_guide_has_webhook_headers(self, auth_headers):
        """Integration guide has webhook headers"""
        response = requests.get(f"{BASE_URL}/api/integration-guide", headers=auth_headers)
        data = response.json()
        assert "webhook_headers" in data, "Missing webhook_headers"
        headers = data["webhook_headers"]
        assert "X-Webhook-Secret" in headers, "Missing X-Webhook-Secret header"
        assert "X-Webhook-Event" in headers, "Missing X-Webhook-Event header"
        print(f"✓ Integration guide has webhook headers")


class TestWebhookDeliveryLog:
    """Webhook Delivery Log tests"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = response.json().get("token")
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.fixture(scope="class")
    def test_webhook(self, auth_headers):
        """Create a test webhook for delivery log testing"""
        # First check if we have an existing webhook
        response = requests.get(f"{BASE_URL}/api/webhooks", headers=auth_headers)
        webhooks = response.json()
        
        # Look for existing test webhook
        for wh in webhooks:
            if "httpbin" in wh.get("url", "") or "Test" in wh.get("label", ""):
                return wh
        
        # Create new test webhook
        response = requests.post(f"{BASE_URL}/api/webhooks", headers=auth_headers, json={
            "url": "https://httpbin.org/post",
            "label": "TEST_DeliveryLogTest",
            "events": ["review.created", "webhook.test"]
        })
        assert response.status_code == 200, f"Failed to create webhook: {response.text}"
        return response.json()
    
    def test_webhook_test_creates_delivery_log(self, auth_headers, test_webhook):
        """POST /api/webhooks/{id}/test creates delivery log entry"""
        webhook_id = test_webhook["id"]
        
        # Send test ping
        response = requests.post(f"{BASE_URL}/api/webhooks/{webhook_id}/test", headers=auth_headers)
        assert response.status_code == 200, f"Test ping failed: {response.text}"
        result = response.json()
        
        # Verify test result structure
        assert "success" in result, "Missing success field"
        assert "response_time_ms" in result, "Missing response_time_ms"
        print(f"✓ Test ping sent: success={result['success']}, time={result.get('response_time_ms')}ms")
        
        # Wait a moment for delivery log to be written
        time.sleep(0.5)
        
        # Fetch delivery log
        log_response = requests.get(f"{BASE_URL}/api/webhooks/{webhook_id}/deliveries", headers=auth_headers)
        assert log_response.status_code == 200, f"Failed to get deliveries: {log_response.text}"
        deliveries = log_response.json()
        
        # Verify delivery log has entries
        assert len(deliveries) > 0, "No delivery log entries found after test ping"
        print(f"✓ Delivery log has {len(deliveries)} entries")
    
    def test_delivery_log_returns_list(self, auth_headers, test_webhook):
        """GET /api/webhooks/{id}/deliveries returns list"""
        webhook_id = test_webhook["id"]
        response = requests.get(f"{BASE_URL}/api/webhooks/{webhook_id}/deliveries", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list), "Deliveries should be a list"
        print(f"✓ Delivery log returns list with {len(data)} entries")
    
    def test_delivery_log_entry_structure(self, auth_headers, test_webhook):
        """Delivery log entries have correct structure"""
        webhook_id = test_webhook["id"]
        response = requests.get(f"{BASE_URL}/api/webhooks/{webhook_id}/deliveries", headers=auth_headers)
        deliveries = response.json()
        
        if len(deliveries) > 0:
            entry = deliveries[0]
            # Check required fields
            assert "id" in entry, "Entry missing id"
            assert "webhook_id" in entry, "Entry missing webhook_id"
            assert "event" in entry, "Entry missing event"
            assert "success" in entry, "Entry missing success"
            assert "timestamp" in entry, "Entry missing timestamp"
            
            # Check optional fields that should be present
            if entry.get("success"):
                assert "status_code" in entry, "Successful entry missing status_code"
                assert "response_time_ms" in entry, "Entry missing response_time_ms"
            
            print(f"✓ Delivery log entry structure valid: event={entry['event']}, success={entry['success']}")
        else:
            pytest.skip("No delivery log entries to verify structure")
    
    def test_delivery_log_shows_event_type(self, auth_headers, test_webhook):
        """Delivery log shows event type"""
        webhook_id = test_webhook["id"]
        response = requests.get(f"{BASE_URL}/api/webhooks/{webhook_id}/deliveries", headers=auth_headers)
        deliveries = response.json()
        
        if len(deliveries) > 0:
            entry = deliveries[0]
            assert "event" in entry, "Entry missing event"
            assert entry["event"] == "webhook.test", f"Expected webhook.test event, got {entry['event']}"
            print(f"✓ Delivery log shows event type: {entry['event']}")
        else:
            pytest.skip("No delivery log entries")
    
    def test_delivery_log_shows_http_status(self, auth_headers, test_webhook):
        """Delivery log shows HTTP status code"""
        webhook_id = test_webhook["id"]
        response = requests.get(f"{BASE_URL}/api/webhooks/{webhook_id}/deliveries", headers=auth_headers)
        deliveries = response.json()
        
        if len(deliveries) > 0:
            entry = deliveries[0]
            if entry.get("success"):
                assert "status_code" in entry, "Entry missing status_code"
                assert entry["status_code"] == 200, f"Expected 200, got {entry['status_code']}"
                print(f"✓ Delivery log shows HTTP status: {entry['status_code']}")
            else:
                print(f"✓ Delivery log entry was not successful (error: {entry.get('error')})")
        else:
            pytest.skip("No delivery log entries")
    
    def test_delivery_log_shows_response_time(self, auth_headers, test_webhook):
        """Delivery log shows response time"""
        webhook_id = test_webhook["id"]
        response = requests.get(f"{BASE_URL}/api/webhooks/{webhook_id}/deliveries", headers=auth_headers)
        deliveries = response.json()
        
        if len(deliveries) > 0:
            entry = deliveries[0]
            assert "response_time_ms" in entry, "Entry missing response_time_ms"
            assert isinstance(entry["response_time_ms"], (int, float)), "response_time_ms should be numeric"
            print(f"✓ Delivery log shows response time: {entry['response_time_ms']}ms")
        else:
            pytest.skip("No delivery log entries")
    
    def test_delivery_log_shows_timestamp(self, auth_headers, test_webhook):
        """Delivery log shows timestamp"""
        webhook_id = test_webhook["id"]
        response = requests.get(f"{BASE_URL}/api/webhooks/{webhook_id}/deliveries", headers=auth_headers)
        deliveries = response.json()
        
        if len(deliveries) > 0:
            entry = deliveries[0]
            assert "timestamp" in entry, "Entry missing timestamp"
            assert len(entry["timestamp"]) > 0, "Timestamp should not be empty"
            print(f"✓ Delivery log shows timestamp: {entry['timestamp']}")
        else:
            pytest.skip("No delivery log entries")
    
    def test_delivery_log_nonexistent_webhook_returns_404(self, auth_headers):
        """GET /api/webhooks/{nonexistent}/deliveries returns 404"""
        response = requests.get(f"{BASE_URL}/api/webhooks/nonexistent-id-12345/deliveries", headers=auth_headers)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print(f"✓ Nonexistent webhook returns 404")
    
    def test_delivery_log_requires_auth(self):
        """GET /api/webhooks/{id}/deliveries requires authentication"""
        response = requests.get(f"{BASE_URL}/api/webhooks/some-id/deliveries")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print(f"✓ Delivery log requires authentication")


class TestSidebarNavigation:
    """Test sidebar has 12 items including Integration Guide"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = response.json().get("token")
        return {"Authorization": f"Bearer {token}"}
    
    def test_reviews_endpoint_works(self, auth_headers):
        """Reviews endpoint works (sidebar item 1)"""
        response = requests.get(f"{BASE_URL}/api/reviews", headers=auth_headers)
        assert response.status_code == 200
        print(f"✓ Reviews endpoint works")
    
    def test_analytics_endpoint_works(self, auth_headers):
        """Analytics endpoint works (sidebar item 2)"""
        response = requests.get(f"{BASE_URL}/api/analytics/dashboard", headers=auth_headers)
        assert response.status_code == 200
        print(f"✓ Analytics endpoint works")
    
    def test_templates_endpoint_works(self, auth_headers):
        """Templates endpoint works (sidebar item 3)"""
        response = requests.get(f"{BASE_URL}/api/templates", headers=auth_headers)
        assert response.status_code == 200
        print(f"✓ Templates endpoint works")
    
    def test_approvals_endpoint_works(self, auth_headers):
        """Approvals endpoint works (sidebar item 4)"""
        response = requests.get(f"{BASE_URL}/api/reviews/pending-approval", headers=auth_headers)
        assert response.status_code == 200
        print(f"✓ Approvals endpoint works")
    
    def test_integrations_endpoint_works(self, auth_headers):
        """Integrations endpoint works (sidebar item 5)"""
        response = requests.get(f"{BASE_URL}/api/integrations", headers=auth_headers)
        assert response.status_code == 200
        print(f"✓ Integrations endpoint works")
    
    def test_api_keys_endpoint_works(self, auth_headers):
        """API Connection endpoint works (sidebar item 6)"""
        response = requests.get(f"{BASE_URL}/api/api-keys", headers=auth_headers)
        assert response.status_code == 200
        print(f"✓ API Connection endpoint works")
    
    def test_webhooks_endpoint_works(self, auth_headers):
        """Webhooks endpoint works (sidebar item 7)"""
        response = requests.get(f"{BASE_URL}/api/webhooks", headers=auth_headers)
        assert response.status_code == 200
        print(f"✓ Webhooks endpoint works")
    
    def test_integration_guide_endpoint_works(self, auth_headers):
        """Integration Guide endpoint works (sidebar item 8 - NEW)"""
        response = requests.get(f"{BASE_URL}/api/integration-guide", headers=auth_headers)
        assert response.status_code == 200
        print(f"✓ Integration Guide endpoint works")
    
    def test_notifications_endpoint_works(self, auth_headers):
        """Alerts/Notifications endpoint works (sidebar item 9)"""
        response = requests.get(f"{BASE_URL}/api/notifications/settings", headers=auth_headers)
        assert response.status_code == 200
        print(f"✓ Alerts endpoint works")
    
    def test_reports_endpoint_works(self, auth_headers):
        """Reports endpoint works (sidebar item 10)"""
        response = requests.get(f"{BASE_URL}/api/reports/settings", headers=auth_headers)
        assert response.status_code == 200
        print(f"✓ Reports endpoint works")
    
    def test_branding_endpoint_works(self, auth_headers):
        """Branding endpoint works (sidebar item 11)"""
        response = requests.get(f"{BASE_URL}/api/branding", headers=auth_headers)
        assert response.status_code == 200
        print(f"✓ Branding endpoint works")
    
    def test_users_endpoint_works(self, auth_headers):
        """Team/Users endpoint works (sidebar item 12)"""
        response = requests.get(f"{BASE_URL}/api/users", headers=auth_headers)
        assert response.status_code == 200
        print(f"✓ Team endpoint works")


class TestExistingFeatures:
    """Verify existing features still work"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = response.json().get("token")
        return {"Authorization": f"Bearer {token}"}
    
    def test_reviews_stats_summary(self, auth_headers):
        """Reviews stats summary works"""
        response = requests.get(f"{BASE_URL}/api/reviews/stats/summary", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_reviews" in data
        assert "average_rating" in data
        assert "response_rate" in data
        print(f"✓ Reviews stats: {data['total_reviews']} reviews, {data['average_rating']}/5 avg, {data['response_rate']}% response rate")
    
    def test_api_key_crud(self, auth_headers):
        """API key CRUD still works"""
        # Create
        response = requests.post(f"{BASE_URL}/api/api-keys", headers=auth_headers, json={"label": "TEST_CRUDTest"})
        assert response.status_code == 200
        key = response.json()
        assert key["key"].startswith("rhk_")
        key_id = key["id"]
        print(f"✓ API key created: {key['key_masked']}")
        
        # List
        response = requests.get(f"{BASE_URL}/api/api-keys", headers=auth_headers)
        assert response.status_code == 200
        keys = response.json()
        assert any(k["id"] == key_id for k in keys)
        print(f"✓ API key appears in list")
        
        # Delete
        response = requests.delete(f"{BASE_URL}/api/api-keys/{key_id}", headers=auth_headers)
        assert response.status_code == 200
        print(f"✓ API key deleted")
    
    def test_webhook_crud(self, auth_headers):
        """Webhook CRUD still works"""
        # Create
        response = requests.post(f"{BASE_URL}/api/webhooks", headers=auth_headers, json={
            "url": "https://example.com/webhook",
            "label": "TEST_CRUDWebhook",
            "events": ["review.created"]
        })
        assert response.status_code == 200
        webhook = response.json()
        webhook_id = webhook["id"]
        print(f"✓ Webhook created: {webhook['label']}")
        
        # List
        response = requests.get(f"{BASE_URL}/api/webhooks", headers=auth_headers)
        assert response.status_code == 200
        webhooks = response.json()
        assert any(w["id"] == webhook_id for w in webhooks)
        print(f"✓ Webhook appears in list")
        
        # Delete
        response = requests.delete(f"{BASE_URL}/api/webhooks/{webhook_id}", headers=auth_headers)
        assert response.status_code == 200
        print(f"✓ Webhook deleted")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
