"""
Iteration 111 - 365-Day Market Demand Dashboard Testing
Tests:
1. GET /api/revenue/market-robot/all/demand-dashboard?days=365 returns 365 daily_data entries
2. GET /api/revenue/market-robot/all/demand-dashboard?days=30 returns 30 entries (nights selector)
3. POST /api/revenue/dynamic-pricing/all/calculate with {days:365} works for full year
4. POST /api/revenue/dynamic-pricing/all/calculate with {days:30} works for 30 days
5. GET /api/revenue/market-robot/all/scanner/status shows 7 tiers (including 3-6 months and 6-12 months)
6. Demand dashboard response structure validation
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://review-hub-108.preview.emergentagent.com"

class TestIteration111_365DayDemand:
    """Tests for 365-day market demand dashboard and dynamic pricing expansion"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        token = login_resp.json().get("token")
        assert token, "No token in login response"
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        yield
    
    # ==================== DEMAND DASHBOARD TESTS ====================
    
    def test_demand_dashboard_365_days(self):
        """Test demand dashboard returns 365 daily_data entries"""
        resp = self.session.get(f"{BASE_URL}/api/revenue/market-robot/all/demand-dashboard?days=365")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        # Verify daily_data has 365 entries
        assert "daily_data" in data, "Missing daily_data in response"
        assert len(data["daily_data"]) == 365, f"Expected 365 entries, got {len(data['daily_data'])}"
        print(f"✓ Demand dashboard returns 365 daily_data entries")
    
    def test_demand_dashboard_30_days(self):
        """Test demand dashboard returns 30 entries with nights selector"""
        resp = self.session.get(f"{BASE_URL}/api/revenue/market-robot/all/demand-dashboard?days=30")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        assert "daily_data" in data, "Missing daily_data in response"
        assert len(data["daily_data"]) == 30, f"Expected 30 entries, got {len(data['daily_data'])}"
        print(f"✓ Demand dashboard returns 30 daily_data entries for nights selector")
    
    def test_demand_dashboard_60_days(self):
        """Test demand dashboard returns 60 entries"""
        resp = self.session.get(f"{BASE_URL}/api/revenue/market-robot/all/demand-dashboard?days=60")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        assert len(data["daily_data"]) == 60, f"Expected 60 entries, got {len(data['daily_data'])}"
        print(f"✓ Demand dashboard returns 60 daily_data entries")
    
    def test_demand_dashboard_90_days(self):
        """Test demand dashboard returns 90 entries"""
        resp = self.session.get(f"{BASE_URL}/api/revenue/market-robot/all/demand-dashboard?days=90")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        assert len(data["daily_data"]) == 90, f"Expected 90 entries, got {len(data['daily_data'])}"
        print(f"✓ Demand dashboard returns 90 daily_data entries")
    
    def test_demand_dashboard_180_days(self):
        """Test demand dashboard returns 180 entries"""
        resp = self.session.get(f"{BASE_URL}/api/revenue/market-robot/all/demand-dashboard?days=180")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        assert len(data["daily_data"]) == 180, f"Expected 180 entries, got {len(data['daily_data'])}"
        print(f"✓ Demand dashboard returns 180 daily_data entries")
    
    def test_demand_dashboard_entry_structure(self):
        """Test each daily_data entry has required fields"""
        resp = self.session.get(f"{BASE_URL}/api/revenue/market-robot/all/demand-dashboard?days=365")
        assert resp.status_code == 200
        data = resp.json()
        
        required_fields = [
            "date", "dow", "occupancy", "market_unavail", "demand_level",
            "base_rate", "ai_rate", "sell_rate", "min_rate", "floor_rate",
            "target_rate", "ai_status", "event", "event_impact"
        ]
        
        # Check first entry
        entry = data["daily_data"][0]
        for field in required_fields:
            assert field in entry, f"Missing field '{field}' in daily_data entry"
        
        # Verify ai_status values
        valid_statuses = ["ai", "event", "manual", "base"]
        assert entry["ai_status"] in valid_statuses, f"Invalid ai_status: {entry['ai_status']}"
        
        # Verify demand_level values
        valid_levels = ["high", "moderate", "low"]
        assert entry["demand_level"] in valid_levels, f"Invalid demand_level: {entry['demand_level']}"
        
        print(f"✓ Daily data entry has all required fields: {required_fields}")
        print(f"  Sample entry: date={entry['date']}, ai_status={entry['ai_status']}, demand_level={entry['demand_level']}")
    
    def test_demand_dashboard_kpis(self):
        """Test KPIs in demand dashboard response"""
        resp = self.session.get(f"{BASE_URL}/api/revenue/market-robot/all/demand-dashboard?days=365")
        assert resp.status_code == 200
        data = resp.json()
        
        assert "kpis" in data, "Missing kpis in response"
        kpis = data["kpis"]
        
        required_kpis = [
            "total_days", "avg_occupancy", "avg_sell_rate", "base_rate",
            "high_demand_days", "low_demand_days", "event_days", "ai_managed_days", "ai_managed_pct"
        ]
        
        for kpi in required_kpis:
            assert kpi in kpis, f"Missing KPI '{kpi}'"
        
        # Verify total_days matches requested days
        assert kpis["total_days"] == 365, f"Expected total_days=365, got {kpis['total_days']}"
        
        print(f"✓ KPIs present: total_days={kpis['total_days']}, avg_occupancy={kpis['avg_occupancy']}%, high_demand={kpis['high_demand_days']}, low_demand={kpis['low_demand_days']}, event_days={kpis['event_days']}, ai_managed={kpis['ai_managed_pct']}%")
    
    # ==================== DYNAMIC PRICING TESTS ====================
    
    def test_dynamic_pricing_calculate_365_days(self):
        """Test dynamic pricing calculation for 365 days"""
        resp = self.session.post(f"{BASE_URL}/api/revenue/dynamic-pricing/all/calculate", json={"days": 365})
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        assert "summary" in data, "Missing summary in response"
        assert data["summary"]["total_days"] == 365, f"Expected 365 days, got {data['summary']['total_days']}"
        
        print(f"✓ Dynamic pricing calculated for 365 days")
        print(f"  Summary: increases={data['summary']['increases']}, decreases={data['summary']['decreases']}, avg_change={data['summary']['avg_change_pct']}%")
    
    def test_dynamic_pricing_calculate_30_days(self):
        """Test dynamic pricing calculation for 30 days"""
        resp = self.session.post(f"{BASE_URL}/api/revenue/dynamic-pricing/all/calculate", json={"days": 30})
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        assert data["summary"]["total_days"] == 30, f"Expected 30 days, got {data['summary']['total_days']}"
        print(f"✓ Dynamic pricing calculated for 30 days")
    
    def test_dynamic_pricing_calculate_60_days(self):
        """Test dynamic pricing calculation for 60 days"""
        resp = self.session.post(f"{BASE_URL}/api/revenue/dynamic-pricing/all/calculate", json={"days": 60})
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        assert data["summary"]["total_days"] == 60, f"Expected 60 days, got {data['summary']['total_days']}"
        print(f"✓ Dynamic pricing calculated for 60 days")
    
    def test_dynamic_pricing_calculate_90_days(self):
        """Test dynamic pricing calculation for 90 days"""
        resp = self.session.post(f"{BASE_URL}/api/revenue/dynamic-pricing/all/calculate", json={"days": 90})
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        assert data["summary"]["total_days"] == 90, f"Expected 90 days, got {data['summary']['total_days']}"
        print(f"✓ Dynamic pricing calculated for 90 days")
    
    def test_dynamic_pricing_calculate_180_days(self):
        """Test dynamic pricing calculation for 180 days"""
        resp = self.session.post(f"{BASE_URL}/api/revenue/dynamic-pricing/all/calculate", json={"days": 180})
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        assert data["summary"]["total_days"] == 180, f"Expected 180 days, got {data['summary']['total_days']}"
        print(f"✓ Dynamic pricing calculated for 180 days")
    
    def test_dynamic_pricing_data_sources(self):
        """Test dynamic pricing includes all data sources"""
        resp = self.session.post(f"{BASE_URL}/api/revenue/dynamic-pricing/all/calculate", json={"days": 365})
        assert resp.status_code == 200
        data = resp.json()
        
        assert "data_sources" in data, "Missing data_sources in response"
        ds = data["data_sources"]
        
        required_sources = ["market_supply_dates", "competitors_with_prices", "strategy_configured", "events_loaded", "historical_floors"]
        for src in required_sources:
            assert src in ds, f"Missing data source '{src}'"
        
        print(f"✓ Data sources: market_supply={ds['market_supply_dates']}, competitors={ds['competitors_with_prices']}, events={ds['events_loaded']}, historical_floors={ds['historical_floors']}")
    
    # ==================== SCANNER STATUS TESTS ====================
    
    def test_scanner_status_7_tiers(self):
        """Test scanner status shows 7 tiers including 3-6 months and 6-12 months"""
        resp = self.session.get(f"{BASE_URL}/api/revenue/market-robot/all/scanner/status")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        assert "tiers" in data, "Missing tiers in response"
        tiers = data["tiers"]
        
        # Should have 7 tiers
        assert len(tiers) == 7, f"Expected 7 tiers, got {len(tiers)}"
        
        # Verify tier labels
        expected_labels = [
            "Today + Tomorrow",
            "Next 3-7 days",
            "1-2 weeks out",
            "2-4 weeks out",
            "1-3 months out",
            "3-6 months out",
            "6-12 months out"
        ]
        
        actual_labels = [t["label"] for t in tiers]
        for label in expected_labels:
            assert label in actual_labels, f"Missing tier '{label}'"
        
        print(f"✓ Scanner status shows 7 tiers: {actual_labels}")
    
    def test_scanner_status_tier_intervals(self):
        """Test scanner tiers have correct intervals"""
        resp = self.session.get(f"{BASE_URL}/api/revenue/market-robot/all/scanner/status")
        assert resp.status_code == 200
        data = resp.json()
        
        tiers = data["tiers"]
        
        # Verify intervals for new tiers
        tier_intervals = {t["label"]: t["interval_mins"] for t in tiers}
        
        assert tier_intervals.get("3-6 months out") == 1440, f"3-6 months tier should be 1440 mins (24h)"
        assert tier_intervals.get("6-12 months out") == 2880, f"6-12 months tier should be 2880 mins (48h)"
        
        print(f"✓ Tier intervals correct: 3-6 months={tier_intervals.get('3-6 months out')}m, 6-12 months={tier_intervals.get('6-12 months out')}m")
    
    def test_scanner_status_structure(self):
        """Test scanner status response structure"""
        resp = self.session.get(f"{BASE_URL}/api/revenue/market-robot/all/scanner/status")
        assert resp.status_code == 200
        data = resp.json()
        
        assert "running" in data, "Missing 'running' field"
        assert "stats" in data, "Missing 'stats' field"
        assert "tiers" in data, "Missing 'tiers' field"
        assert "event_scan_interval_mins" in data, "Missing 'event_scan_interval_mins' field"
        
        print(f"✓ Scanner status structure valid: running={data['running']}, event_scan_interval={data['event_scan_interval_mins']}m")
    
    # ==================== MARKET ROBOT CONFIG TESTS ====================
    
    def test_market_robot_config_endpoint_works(self):
        """Test market robot config endpoint returns valid response"""
        resp = self.session.get(f"{BASE_URL}/api/revenue/market-robot/all/config")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        # Verify config has required fields
        assert "property_id" in data, "Missing property_id"
        assert "city" in data, "Missing city"
        assert "auto_pricing" in data, "Missing auto_pricing"
        assert "days_ahead" in data, "Missing days_ahead"
        
        # Note: days_ahead may be user-configured, but code default is 365
        print(f"✓ Market robot config endpoint works: city={data.get('city')}, days_ahead={data.get('days_ahead')}, auto_pricing={data.get('auto_pricing')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
