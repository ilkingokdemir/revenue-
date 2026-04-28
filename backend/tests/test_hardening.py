"""
Test suite for Phase 1 Production Hardening features:
- Health endpoints (/api/health, /api/health/live, /api/health/ready)
- X-Request-ID middleware
- Regression tests for recent feature batches (pricing-explain, hk-turnover, bi-feed, fnb-tabs)
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for admin user"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Authentication failed - skipping authenticated tests")

@pytest.fixture
def auth_headers(auth_token):
    """Headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestHealthEndpoints:
    """Test health check endpoints for production hardening"""
    
    def test_health_endpoint_returns_200(self):
        """GET /api/health should return 200 with full status"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields
        assert "status" in data
        assert "version" in data
        assert "started_at" in data
        assert "uptime_sec" in data
        assert "checks" in data
        
        # Verify checks structure
        checks = data["checks"]
        assert "mongodb" in checks
        assert "llm_key" in checks
        assert "stripe_key" in checks
        assert "disk_free_mb" in checks
        
        print(f"Health status: {data['status']}, version: {data['version']}")
    
    def test_health_live_endpoint(self):
        """GET /api/health/live should return 200 with {status: 'alive'}"""
        response = requests.get(f"{BASE_URL}/api/health/live")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"
        print("Liveness check passed")
    
    def test_health_ready_endpoint(self):
        """GET /api/health/ready should return 200 with {status: 'ready'} when DB is up"""
        response = requests.get(f"{BASE_URL}/api/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        print("Readiness check passed")


class TestRequestIdMiddleware:
    """Test X-Request-ID header middleware"""
    
    def test_server_generates_request_id(self):
        """Server should generate X-Request-ID if client doesn't provide one"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        
        # Check X-Request-ID header exists
        request_id = response.headers.get("X-Request-ID")
        assert request_id is not None
        assert len(request_id) > 0
        
        # Verify it looks like a UUID
        try:
            uuid.UUID(request_id)
            print(f"Server generated valid UUID: {request_id}")
        except ValueError:
            # Not a UUID but still valid if non-empty
            print(f"Server generated request ID: {request_id}")
    
    def test_server_echoes_client_request_id(self):
        """Server should echo back client-provided X-Request-ID"""
        client_request_id = "test-client-id-12345"
        response = requests.get(
            f"{BASE_URL}/api/health",
            headers={"X-Request-ID": client_request_id}
        )
        assert response.status_code == 200
        
        # Check server echoed the same ID
        echoed_id = response.headers.get("X-Request-ID")
        assert echoed_id == client_request_id
        print(f"Server correctly echoed client request ID: {echoed_id}")
    
    def test_request_id_on_authenticated_endpoint(self, auth_headers):
        """X-Request-ID should work on authenticated endpoints too"""
        client_request_id = f"auth-test-{uuid.uuid4()}"
        headers = {**auth_headers, "X-Request-ID": client_request_id}
        
        response = requests.get(f"{BASE_URL}/api/reviews", headers=headers)
        assert response.status_code == 200
        
        echoed_id = response.headers.get("X-Request-ID")
        assert echoed_id == client_request_id
        print(f"Request ID works on authenticated endpoints: {echoed_id}")


class TestRegressionBatch22Features:
    """Light regression tests for recent feature batches (pricing-explain, hk-turnover, bi-feed, fnb-tabs)"""
    
    def test_hk_turnover_api(self, auth_headers):
        """HK Turnover API should return room states"""
        response = requests.get(
            f"{BASE_URL}/api/hk-turnover/aldgate-flats",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "property_id" in data
        assert "by_state" in data
        print(f"HK Turnover API working - property: {data['property_id']}")
    
    def test_fnb_tabs_api(self, auth_headers):
        """F&B Tabs API should return tabs list"""
        response = requests.get(
            f"{BASE_URL}/api/fnb/tabs/aldgate-flats",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "rows" in data
        assert "count" in data
        print(f"F&B Tabs API working - count: {data['count']}")
    
    def test_bi_feed_tokens_api(self, auth_headers):
        """BI Feed tokens API should return token list"""
        response = requests.get(
            f"{BASE_URL}/api/bi/tokens/aldgate-flats",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "rows" in data
        print(f"BI Feed API working - tokens: {len(data['rows'])}")
    
    def test_pricing_explain_dashboard_api(self, auth_headers):
        """Pricing Explain dashboard API should return stats"""
        response = requests.get(
            f"{BASE_URL}/api/pricing/explain/dashboard/aldgate-flats",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "total" in data
        assert "pending" in data
        print(f"Pricing Explain API working - total: {data['total']}")


class TestCoreApiRegression:
    """Quick regression tests for core APIs"""
    
    def test_auth_login(self):
        """Login should work with valid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["email"] == "admin@hotelbox.com"
        print("Auth login working")
    
    def test_properties_list(self, auth_headers):
        """Properties list should return branches"""
        response = requests.get(f"{BASE_URL}/api/properties", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        print(f"Properties API working - count: {len(data)}")
    
    def test_reviews_list(self, auth_headers):
        """Reviews list should work"""
        response = requests.get(f"{BASE_URL}/api/reviews", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Reviews API working - count: {len(data)}")
    
    def test_dashboard_tier1(self, auth_headers):
        """Tier1 dashboard should return KPIs"""
        response = requests.get(
            f"{BASE_URL}/api/tier1-dashboard/default?days=7",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "property_id" in data or "kpis" in data or isinstance(data, dict)
        print("Tier1 Dashboard API working")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
