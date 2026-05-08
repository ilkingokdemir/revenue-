"""
Test Help & User Guide endpoints (Iteration 254)
- GET /api/help/manual — returns full markdown manual (>10KB)
- GET /api/help/index — returns sections array (>50 items)
- GET /api/help/video-script — returns video script markdown
- All endpoints require authentication
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestHelpEndpoints:
    """Help & User Guide endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: login as admin to get auth cookie"""
        self.session = requests.Session()
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        self.auth_token = login_resp.json().get("access_token")
        if self.auth_token:
            self.session.headers.update({"Authorization": f"Bearer {self.auth_token}"})
    
    def test_help_manual_returns_200_with_content(self):
        """GET /api/help/manual returns 200 with JSON {format, content, version}"""
        resp = self.session.get(f"{BASE_URL}/api/help/manual")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "format" in data, "Response missing 'format' field"
        assert "content" in data, "Response missing 'content' field"
        assert "version" in data, "Response missing 'version' field"
        assert data["format"] == "markdown", f"Expected format='markdown', got {data['format']}"
        
        # Content should be >10KB (10000 bytes)
        content_len = len(data["content"])
        assert content_len > 10000, f"Manual content too small: {content_len} bytes (expected >10KB)"
        print(f"✓ Manual content size: {content_len} bytes")
    
    def test_help_index_returns_sections_array(self):
        """GET /api/help/index returns 200 with sections array (>50 items)"""
        resp = self.session.get(f"{BASE_URL}/api/help/index")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "sections" in data, "Response missing 'sections' field"
        assert isinstance(data["sections"], list), "sections should be a list"
        
        sections = data["sections"]
        assert len(sections) > 50, f"Expected >50 sections, got {len(sections)}"
        
        # Validate section structure
        for section in sections[:5]:  # Check first 5
            assert "level" in section, f"Section missing 'level': {section}"
            assert "title" in section, f"Section missing 'title': {section}"
            assert "anchor" in section, f"Section missing 'anchor': {section}"
        
        print(f"✓ Index has {len(sections)} sections")
    
    def test_help_video_script_returns_content(self):
        """GET /api/help/video-script returns 200 with non-empty markdown"""
        resp = self.session.get(f"{BASE_URL}/api/help/video-script")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "format" in data, "Response missing 'format' field"
        assert "content" in data, "Response missing 'content' field"
        assert data["format"] == "markdown", f"Expected format='markdown', got {data['format']}"
        
        content_len = len(data["content"])
        assert content_len > 5000, f"Video script too small: {content_len} bytes (expected >5KB)"
        print(f"✓ Video script size: {content_len} bytes")
    
    def test_help_endpoints_reject_unauthenticated(self):
        """All help endpoints should reject unauthenticated requests with 401"""
        unauth_session = requests.Session()
        
        endpoints = [
            "/api/help/manual",
            "/api/help/index",
            "/api/help/video-script"
        ]
        
        for endpoint in endpoints:
            resp = unauth_session.get(f"{BASE_URL}{endpoint}")
            assert resp.status_code == 401, f"{endpoint} should return 401 for unauthenticated, got {resp.status_code}"
            print(f"✓ {endpoint} correctly rejects unauthenticated requests")


class TestRegressionPanels:
    """Light regression tests for existing panels"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: login as admin"""
        self.session = requests.Session()
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        self.auth_token = login_resp.json().get("access_token")
        if self.auth_token:
            self.session.headers.update({"Authorization": f"Bearer {self.auth_token}"})
    
    def test_pricing_explain_endpoint(self):
        """GET /api/pricing-explain/config returns 200"""
        resp = self.session.get(f"{BASE_URL}/api/pricing-explain/config")
        # May return 200 or 404 if no config exists
        assert resp.status_code in [200, 404], f"Unexpected status: {resp.status_code}"
        print(f"✓ pricing-explain/config: {resp.status_code}")
    
    def test_hk_turnover_endpoint(self):
        """GET /api/hk-turnover/stats returns 200"""
        resp = self.session.get(f"{BASE_URL}/api/hk-turnover/stats")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        print(f"✓ hk-turnover/stats: {resp.status_code}")
    
    def test_banquet_orders_endpoint(self):
        """GET /api/banquet-orders/default returns 200"""
        resp = self.session.get(f"{BASE_URL}/api/banquet-orders/default")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        print(f"✓ banquet-orders/default: {resp.status_code}")
    
    def test_loyalty_tier_endpoint(self):
        """GET /api/loyalty-tier/config/default returns 200"""
        resp = self.session.get(f"{BASE_URL}/api/loyalty-tier/config/default")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        print(f"✓ loyalty-tier/config/default: {resp.status_code}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
