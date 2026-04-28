"""
Test AI Copilot endpoints (Batch 28)
- POST /api/copilot/summarize: universal GPT-5.2 summarize endpoint
- GET /api/copilot/recent: recent cached entries
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"

class TestCopilotEndpoints:
    """AI Copilot endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session with auth"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login as admin
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        self.token = login_resp.json().get("access_token")
        if self.token:
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    # ========== POST /api/copilot/summarize tests ==========
    
    def test_summarize_kpis_context(self):
        """Test summarize with kpis context_type"""
        payload = {
            "context_type": "kpis",
            "data": {
                "occupancy": 78,
                "adr": 120,
                "revpar": 93.6,
                "total_revenue": 45000
            },
            "property_id": "default"
        }
        resp = self.session.post(f"{BASE_URL}/api/copilot/summarize", json=payload)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "insight" in data, "Response should contain 'insight'"
        assert "suggested_actions" in data, "Response should contain 'suggested_actions'"
        assert "source" in data, "Response should contain 'source'"
        assert "key" in data, "Response should contain 'key' (cache key)"
        assert isinstance(data["suggested_actions"], list), "suggested_actions should be a list"
        assert len(data["insight"]) > 0, "insight should not be empty"
        print(f"✓ KPIs summarize: source={data['source']}, insight length={len(data['insight'])}")
    
    def test_summarize_anomaly_context(self):
        """Test summarize with anomaly context_type"""
        payload = {
            "context_type": "anomaly",
            "data": {
                "metric": "revenue",
                "expected": 5000,
                "actual": 2500,
                "deviation": -50,
                "date": "2026-01-15"
            }
        }
        resp = self.session.post(f"{BASE_URL}/api/copilot/summarize", json=payload)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "insight" in data
        assert "suggested_actions" in data
        assert len(data["suggested_actions"]) > 0, "Should have at least one action"
        print(f"✓ Anomaly summarize: {len(data['suggested_actions'])} actions")
    
    def test_summarize_timeseries_context(self):
        """Test summarize with timeseries context_type"""
        payload = {
            "context_type": "timeseries",
            "data": {
                "metric": "occupancy",
                "values": [65, 70, 72, 78, 82, 85, 80]
            }
        }
        resp = self.session.post(f"{BASE_URL}/api/copilot/summarize", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "insight" in data
        print(f"✓ Timeseries summarize: source={data['source']}")
    
    def test_summarize_leaderboard_context(self):
        """Test summarize with leaderboard context_type"""
        payload = {
            "context_type": "leaderboard",
            "data": {
                "items": [
                    {"name": "Ali", "score": 95},
                    {"name": "Mehmet", "score": 88},
                    {"name": "Ayşe", "score": 72}
                ]
            }
        }
        resp = self.session.post(f"{BASE_URL}/api/copilot/summarize", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "insight" in data
        print(f"✓ Leaderboard summarize: source={data['source']}")
    
    def test_summarize_inquiry_context(self):
        """Test summarize with inquiry (MICE) context_type"""
        payload = {
            "context_type": "inquiry",
            "data": {
                "event_type": "conference",
                "attendees": 150,
                "dates": "2026-03-15 to 2026-03-17",
                "budget": 25000
            }
        }
        resp = self.session.post(f"{BASE_URL}/api/copilot/summarize", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "insight" in data
        print(f"✓ Inquiry summarize: source={data['source']}")
    
    def test_summarize_forecast_context(self):
        """Test summarize with forecast context_type"""
        payload = {
            "context_type": "forecast",
            "data": {
                "months": ["Jan", "Feb", "Mar"],
                "occupancy_forecast": [65, 72, 85],
                "revenue_forecast": [40000, 48000, 60000]
            }
        }
        resp = self.session.post(f"{BASE_URL}/api/copilot/summarize", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "insight" in data
        print(f"✓ Forecast summarize: source={data['source']}")
    
    def test_summarize_custom_context_with_query(self):
        """Test summarize with custom context_type and user query"""
        payload = {
            "context_type": "custom",
            "data": {"general_query": True},
            "query": "Bu hafta hangi segmentte gelir düştü?"
        }
        resp = self.session.post(f"{BASE_URL}/api/copilot/summarize", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "insight" in data
        print(f"✓ Custom summarize with query: source={data['source']}")
    
    def test_summarize_invalid_context_type_returns_400(self):
        """Test that invalid context_type returns 400"""
        payload = {
            "context_type": "invalid_type",
            "data": {"test": "data"}
        }
        resp = self.session.post(f"{BASE_URL}/api/copilot/summarize", json=payload)
        assert resp.status_code == 400, f"Expected 400 for invalid context_type, got {resp.status_code}"
        print("✓ Invalid context_type correctly returns 400")
    
    def test_summarize_caching_same_payload(self):
        """Test that same payload returns cached=True on second call"""
        # Use unique data to avoid collision with other tests
        unique_data = {
            "context_type": "kpis",
            "data": {
                "test_cache": True,
                "timestamp": time.time(),
                "occupancy": 99,
                "adr": 999
            }
        }
        
        # First call - should not be cached
        resp1 = self.session.post(f"{BASE_URL}/api/copilot/summarize", json=unique_data)
        assert resp1.status_code == 200
        data1 = resp1.json()
        key1 = data1.get("key")
        cached1 = data1.get("cached", False)
        print(f"First call: cached={cached1}, key={key1}")
        
        # Second call with same payload - should be cached
        resp2 = self.session.post(f"{BASE_URL}/api/copilot/summarize", json=unique_data)
        assert resp2.status_code == 200
        data2 = resp2.json()
        cached2 = data2.get("cached", False)
        key2 = data2.get("key")
        
        assert key1 == key2, "Cache keys should match for same payload"
        assert cached2 == True, f"Second call should return cached=True, got {cached2}"
        print(f"✓ Caching works: second call returned cached=True")
    
    def test_summarize_source_is_llm_or_heuristic(self):
        """Test that source is either 'llm', 'llm_raw', or 'heuristic'"""
        payload = {
            "context_type": "kpis",
            "data": {"occupancy": 50, "adr": 100}
        }
        resp = self.session.post(f"{BASE_URL}/api/copilot/summarize", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] in ["llm", "llm_raw", "heuristic"], f"Unexpected source: {data['source']}"
        print(f"✓ Source is valid: {data['source']}")
    
    # ========== GET /api/copilot/recent tests ==========
    
    def test_recent_default_limit(self):
        """Test GET /api/copilot/recent with default limit"""
        resp = self.session.get(f"{BASE_URL}/api/copilot/recent")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "rows" in data, "Response should contain 'rows'"
        assert "count" in data, "Response should contain 'count'"
        assert isinstance(data["rows"], list), "rows should be a list"
        print(f"✓ Recent endpoint: {data['count']} rows returned")
    
    def test_recent_with_limit(self):
        """Test GET /api/copilot/recent with custom limit"""
        resp = self.session.get(f"{BASE_URL}/api/copilot/recent?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["rows"]) <= 5, "Should return at most 5 rows"
        print(f"✓ Recent with limit=5: {len(data['rows'])} rows")
    
    def test_recent_invalid_limit_below_1(self):
        """Test that limit < 1 returns 400"""
        resp = self.session.get(f"{BASE_URL}/api/copilot/recent?limit=0")
        assert resp.status_code == 400, f"Expected 400 for limit=0, got {resp.status_code}"
        print("✓ limit=0 correctly returns 400")
    
    def test_recent_invalid_limit_above_100(self):
        """Test that limit > 100 returns 400"""
        resp = self.session.get(f"{BASE_URL}/api/copilot/recent?limit=101")
        assert resp.status_code == 400, f"Expected 400 for limit=101, got {resp.status_code}"
        print("✓ limit=101 correctly returns 400")
    
    def test_recent_rows_have_required_fields(self):
        """Test that recent rows have required fields"""
        # First create some data
        self.session.post(f"{BASE_URL}/api/copilot/summarize", json={
            "context_type": "kpis",
            "data": {"test": "recent_fields"}
        })
        
        resp = self.session.get(f"{BASE_URL}/api/copilot/recent?limit=1")
        assert resp.status_code == 200
        data = resp.json()
        
        if data["count"] > 0:
            row = data["rows"][0]
            assert "key" in row, "Row should have 'key'"
            assert "context_type" in row, "Row should have 'context_type'"
            assert "insight" in row, "Row should have 'insight'"
            assert "suggested_actions" in row, "Row should have 'suggested_actions'"
            assert "source" in row, "Row should have 'source'"
            assert "created_at" in row, "Row should have 'created_at'"
            print(f"✓ Recent row has all required fields: context_type={row['context_type']}")
    
    # ========== Auth tests ==========
    
    def test_summarize_requires_auth(self):
        """Test that summarize endpoint requires authentication"""
        # Create new session without auth
        no_auth_session = requests.Session()
        no_auth_session.headers.update({"Content-Type": "application/json"})
        
        resp = no_auth_session.post(f"{BASE_URL}/api/copilot/summarize", json={
            "context_type": "kpis",
            "data": {"test": "no_auth"}
        })
        assert resp.status_code in [401, 403], f"Expected 401/403 without auth, got {resp.status_code}"
        print("✓ Summarize requires authentication")
    
    def test_recent_requires_auth(self):
        """Test that recent endpoint requires authentication"""
        no_auth_session = requests.Session()
        resp = no_auth_session.get(f"{BASE_URL}/api/copilot/recent")
        assert resp.status_code in [401, 403], f"Expected 401/403 without auth, got {resp.status_code}"
        print("✓ Recent requires authentication")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
