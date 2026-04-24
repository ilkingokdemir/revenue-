"""
Iteration 169 - Market Robot 60/90 Day Scan Options Testing

Tests:
1. POST /api/revenue/market-robot/{pid}/competitors/scan with days_ahead=90
2. GET /api/revenue/market-robot/{pid}/geo-supply - competitor_series includes hit_rate, attempted_days
3. Verify _auto_our_hotel_scan accepts days_ahead kwarg (1-90 clamped)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestMarketRobotDaysAhead:
    """Test Market Robot 60/90 day scan options"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        token = login_resp.json().get("token")
        assert token, "No access token returned"
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        self.property_id = "default"  # Zurich property with 6 competitors
        yield
        self.session.close()
    
    def test_health_check(self):
        """Verify API is accessible"""
        resp = self.session.get(f"{BASE_URL}/api/health")
        assert resp.status_code == 200
        print("✓ Health check passed")
    
    def test_get_competitors_list(self):
        """Verify competitors exist for default property"""
        resp = self.session.get(f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/competitors")
        assert resp.status_code == 200
        data = resp.json()
        competitors = data.get("competitors", [])
        print(f"✓ Found {len(competitors)} competitors for {self.property_id}")
        assert len(competitors) > 0, "No competitors configured for testing"
        return competitors
    
    def test_scan_competitors_with_90_days(self):
        """Test POST /competitors/scan with days_ahead=90"""
        resp = self.session.post(
            f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/competitors/scan",
            json={"days_ahead": 90}
        )
        assert resp.status_code == 200, f"Scan failed: {resp.text}"
        data = resp.json()
        
        # Verify response structure
        assert data.get("status") == "queued", f"Expected status=queued, got {data.get('status')}"
        assert data.get("days_ahead") == 90, f"Expected days_ahead=90, got {data.get('days_ahead')}"
        assert "total_competitors" in data, "Missing total_competitors in response"
        assert data.get("total_competitors") > 0, "No competitors queued"
        
        print(f"✓ Scan queued: {data.get('total_competitors')} competitors, {data.get('days_ahead')} days")
        return data
    
    def test_scan_competitors_with_60_days(self):
        """Test POST /competitors/scan with days_ahead=60"""
        resp = self.session.post(
            f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/competitors/scan",
            json={"days_ahead": 60}
        )
        assert resp.status_code == 200, f"Scan failed: {resp.text}"
        data = resp.json()
        
        assert data.get("days_ahead") == 60, f"Expected days_ahead=60, got {data.get('days_ahead')}"
        print(f"✓ Scan queued with 60 days: {data.get('total_competitors')} competitors")
        return data
    
    def test_scan_competitors_with_30_days(self):
        """Test POST /competitors/scan with days_ahead=30 (default)"""
        resp = self.session.post(
            f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/competitors/scan",
            json={"days_ahead": 30}
        )
        assert resp.status_code == 200, f"Scan failed: {resp.text}"
        data = resp.json()
        
        assert data.get("days_ahead") == 30, f"Expected days_ahead=30, got {data.get('days_ahead')}"
        print(f"✓ Scan queued with 30 days: {data.get('total_competitors')} competitors")
        return data
    
    def test_scan_competitors_with_7_days(self):
        """Test POST /competitors/scan with days_ahead=7"""
        resp = self.session.post(
            f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/competitors/scan",
            json={"days_ahead": 7}
        )
        assert resp.status_code == 200, f"Scan failed: {resp.text}"
        data = resp.json()
        
        assert data.get("days_ahead") == 7, f"Expected days_ahead=7, got {data.get('days_ahead')}"
        print(f"✓ Scan queued with 7 days: {data.get('total_competitors')} competitors")
        return data
    
    def test_scan_competitors_with_15_days(self):
        """Test POST /competitors/scan with days_ahead=15"""
        resp = self.session.post(
            f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/competitors/scan",
            json={"days_ahead": 15}
        )
        assert resp.status_code == 200, f"Scan failed: {resp.text}"
        data = resp.json()
        
        assert data.get("days_ahead") == 15, f"Expected days_ahead=15, got {data.get('days_ahead')}"
        print(f"✓ Scan queued with 15 days: {data.get('total_competitors')} competitors")
        return data
    
    def test_scan_competitors_clamped_to_90(self):
        """Test that days_ahead > 90 is clamped to 90"""
        resp = self.session.post(
            f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/competitors/scan",
            json={"days_ahead": 120}  # Should be clamped to 90
        )
        assert resp.status_code == 200, f"Scan failed: {resp.text}"
        data = resp.json()
        
        assert data.get("days_ahead") == 90, f"Expected days_ahead clamped to 90, got {data.get('days_ahead')}"
        print(f"✓ days_ahead=120 correctly clamped to 90")
        return data
    
    def test_scan_competitors_clamped_to_1(self):
        """Test that days_ahead < 1 is clamped to 1"""
        resp = self.session.post(
            f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/competitors/scan",
            json={"days_ahead": 0}  # Should be clamped to 1
        )
        assert resp.status_code == 200, f"Scan failed: {resp.text}"
        data = resp.json()
        
        assert data.get("days_ahead") == 1, f"Expected days_ahead clamped to 1, got {data.get('days_ahead')}"
        print(f"✓ days_ahead=0 correctly clamped to 1")
        return data
    
    def test_geo_supply_competitor_series_fields(self):
        """Test GET /geo-supply returns competitor_series with hit_rate and attempted_days"""
        resp = self.session.get(
            f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/geo-supply?days=30"
        )
        assert resp.status_code == 200, f"Geo supply failed: {resp.text}"
        data = resp.json()
        
        competitor_series = data.get("competitor_series", [])
        print(f"✓ Found {len(competitor_series)} competitors in series")
        
        if len(competitor_series) > 0:
            # Check first competitor has required fields
            comp = competitor_series[0]
            assert "hit_rate" in comp, f"Missing hit_rate field in competitor_series: {comp.keys()}"
            assert "attempted_days" in comp, f"Missing attempted_days field in competitor_series: {comp.keys()}"
            assert "days_covered" in comp, f"Missing days_covered field in competitor_series: {comp.keys()}"
            
            # Verify hit_rate is a number 0-100
            hit_rate = comp.get("hit_rate")
            assert isinstance(hit_rate, (int, float)), f"hit_rate should be numeric, got {type(hit_rate)}"
            assert 0 <= hit_rate <= 100, f"hit_rate should be 0-100, got {hit_rate}"
            
            # Verify attempted_days is an integer
            attempted = comp.get("attempted_days")
            assert isinstance(attempted, int), f"attempted_days should be int, got {type(attempted)}"
            
            print(f"✓ Competitor '{comp.get('name')}': hit_rate={hit_rate}%, attempted_days={attempted}, days_covered={comp.get('days_covered')}")
        
        return data
    
    def test_geo_supply_all_competitor_fields(self):
        """Verify all competitors in series have the new fields"""
        resp = self.session.get(
            f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/geo-supply?days=30"
        )
        assert resp.status_code == 200
        data = resp.json()
        
        competitor_series = data.get("competitor_series", [])
        for comp in competitor_series:
            name = comp.get("name", "Unknown")
            assert "hit_rate" in comp, f"Competitor '{name}' missing hit_rate"
            assert "attempted_days" in comp, f"Competitor '{name}' missing attempted_days"
            assert "days_covered" in comp, f"Competitor '{name}' missing days_covered"
            assert "last_scraped" in comp, f"Competitor '{name}' missing last_scraped"
            
            print(f"  - {name}: hit_rate={comp.get('hit_rate')}%, days={comp.get('days_covered')}/{comp.get('attempted_days')}")
        
        print(f"✓ All {len(competitor_series)} competitors have required fields")
        return competitor_series
    
    def test_geo_config_days_options(self):
        """Test geo-config accepts 7/15/30/60/90 days"""
        for days in [7, 15, 30, 60, 90]:
            resp = self.session.put(
                f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/geo-config",
                json={"days_ahead": days, "location": "Zurich", "radius_km": 3.2}
            )
            assert resp.status_code == 200, f"Geo config update failed for days={days}: {resp.text}"
            data = resp.json()
            assert data.get("days_ahead") == days, f"Expected days_ahead={days}, got {data.get('days_ahead')}"
            print(f"✓ Geo config accepts days_ahead={days}")
    
    def test_geo_config_no_14_day_option(self):
        """Verify 14-day option is not special-cased (should work but not be a preset)"""
        resp = self.session.put(
            f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/geo-config",
            json={"days_ahead": 14, "location": "Zurich", "radius_km": 3.2}
        )
        assert resp.status_code == 200
        data = resp.json()
        # 14 should work but is not a preset option in UI
        assert data.get("days_ahead") == 14
        print("✓ days_ahead=14 works but is not a UI preset")


class TestMarketRobotConfig:
    """Test Market Robot configuration endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200
        token = login_resp.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        self.property_id = "default"
        yield
        self.session.close()
    
    def test_get_market_robot_config(self):
        """Test GET /config returns expected structure"""
        resp = self.session.get(f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/config")
        assert resp.status_code == 200
        data = resp.json()
        
        # Verify config structure
        assert "property_id" in data
        assert "enabled" in data
        assert "city" in data
        assert "days_ahead" in data
        assert "currency" in data
        
        print(f"✓ Config: city={data.get('city')}, currency={data.get('currency')}, days_ahead={data.get('days_ahead')}")
        return data


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
