"""
Iteration 110 - Scanner Performance Report Testing
Tests the new Performance Report sub-tab in Market Robot that shows ROI metrics.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestPerformanceReportAPI:
    """Test the /api/revenue/market-robot/{property_id}/performance endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        self.token = login_resp.json().get("token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_performance_endpoint_returns_200(self):
        """GET /api/revenue/market-robot/all/performance returns 200"""
        resp = requests.get(f"{BASE_URL}/api/revenue/market-robot/all/performance", headers=self.headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        print("PASS: Performance endpoint returns 200")
    
    def test_performance_kpis_structure(self):
        """Performance response contains all required KPI fields"""
        resp = requests.get(f"{BASE_URL}/api/revenue/market-robot/all/performance", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        
        # Check kpis object exists
        assert "kpis" in data, "Missing 'kpis' in response"
        kpis = data["kpis"]
        
        # Required KPI fields
        required_kpis = [
            "estimated_revenue_uplift",
            "monthly_revenue_uplift", 
            "total_days_adjusted",
            "avg_uplift_per_day",
            "increases",
            "decreases",
            "event_boost_days",
            "event_revenue_uplift",
            "total_scans",
            "total_events_detected"
        ]
        
        for field in required_kpis:
            assert field in kpis, f"Missing KPI field: {field}"
            print(f"  - {field}: {kpis[field]}")
        
        print("PASS: All required KPI fields present")
    
    def test_performance_by_source_breakdown(self):
        """Performance response contains by_source breakdown with 4 sources"""
        resp = requests.get(f"{BASE_URL}/api/revenue/market-robot/all/performance", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        
        assert "by_source" in data, "Missing 'by_source' in response"
        by_source = data["by_source"]
        
        # Required sources
        required_sources = ["auto_scanner", "market_robot", "ai_dynamic_pricing", "event_intelligence"]
        
        for source in required_sources:
            assert source in by_source, f"Missing source: {source}"
            print(f"  - {source}: £{by_source[source]}")
        
        print("PASS: All 4 revenue sources present in by_source breakdown")
    
    def test_performance_daily_impact_array(self):
        """Performance response contains daily_impact array with correct structure"""
        resp = requests.get(f"{BASE_URL}/api/revenue/market-robot/all/performance", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        
        assert "daily_impact" in data, "Missing 'daily_impact' in response"
        daily_impact = data["daily_impact"]
        
        assert isinstance(daily_impact, list), "daily_impact should be a list"
        
        if len(daily_impact) > 0:
            # Check first item structure
            item = daily_impact[0]
            required_fields = ["date", "base_rate", "robot_rate", "uplift", "uplift_pct", "source", "has_event"]
            
            for field in required_fields:
                assert field in item, f"Missing field in daily_impact item: {field}"
            
            print(f"  - Sample: {item['date']} | Base: £{item['base_rate']} | Robot: £{item['robot_rate']} | Uplift: £{item['uplift']} ({item['uplift_pct']}%) | Source: {item['source']} | Event: {item['has_event']}")
        
        print(f"PASS: daily_impact array has {len(daily_impact)} items with correct structure")
    
    def test_performance_monthly_impact_array(self):
        """Performance response contains monthly_impact array with correct structure"""
        resp = requests.get(f"{BASE_URL}/api/revenue/market-robot/all/performance", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        
        assert "monthly_impact" in data, "Missing 'monthly_impact' in response"
        monthly_impact = data["monthly_impact"]
        
        assert isinstance(monthly_impact, list), "monthly_impact should be a list"
        
        if len(monthly_impact) > 0:
            # Check first item structure
            item = monthly_impact[0]
            required_fields = ["month", "month_label", "uplift_per_room", "est_revenue_uplift", "days_adjusted", "increases", "decreases", "event_days"]
            
            for field in required_fields:
                assert field in item, f"Missing field in monthly_impact item: {field}"
            
            print(f"  - Sample: {item['month_label']} | Uplift: £{item['est_revenue_uplift']} | Days: {item['days_adjusted']} | Events: {item['event_days']}")
        
        print(f"PASS: monthly_impact array has {len(monthly_impact)} items with correct structure")
    
    def test_performance_kpi_values_are_numeric(self):
        """All KPI values should be numeric (int or float)"""
        resp = requests.get(f"{BASE_URL}/api/revenue/market-robot/all/performance", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        
        kpis = data["kpis"]
        for key, value in kpis.items():
            assert isinstance(value, (int, float)), f"KPI {key} should be numeric, got {type(value)}"
        
        print("PASS: All KPI values are numeric")
    
    def test_performance_by_source_values_are_numeric(self):
        """All by_source values should be numeric"""
        resp = requests.get(f"{BASE_URL}/api/revenue/market-robot/all/performance", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        
        by_source = data["by_source"]
        for key, value in by_source.items():
            assert isinstance(value, (int, float)), f"by_source {key} should be numeric, got {type(value)}"
        
        print("PASS: All by_source values are numeric")
    
    def test_performance_daily_impact_sorted_descending(self):
        """daily_impact should be sorted by date descending (most recent first)"""
        resp = requests.get(f"{BASE_URL}/api/revenue/market-robot/all/performance", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        
        daily_impact = data["daily_impact"]
        if len(daily_impact) > 1:
            dates = [item["date"] for item in daily_impact]
            # Check descending order
            for i in range(len(dates) - 1):
                assert dates[i] >= dates[i+1], f"daily_impact not sorted descending: {dates[i]} < {dates[i+1]}"
        
        print("PASS: daily_impact is sorted by date descending")
    
    def test_performance_monthly_impact_sorted_ascending(self):
        """monthly_impact should be sorted by month ascending"""
        resp = requests.get(f"{BASE_URL}/api/revenue/market-robot/all/performance", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        
        monthly_impact = data["monthly_impact"]
        if len(monthly_impact) > 1:
            months = [item["month"] for item in monthly_impact]
            # Check ascending order
            for i in range(len(months) - 1):
                assert months[i] <= months[i+1], f"monthly_impact not sorted ascending: {months[i]} > {months[i+1]}"
        
        print("PASS: monthly_impact is sorted by month ascending")


class TestMarketRobotSubTabs:
    """Test that Market Robot has all 10 sub-tabs"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200
        self.token = login_resp.json().get("token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_market_robot_config_endpoint(self):
        """GET /api/revenue/market-robot/all/config works"""
        resp = requests.get(f"{BASE_URL}/api/revenue/market-robot/all/config", headers=self.headers)
        assert resp.status_code == 200
        print("PASS: Config endpoint works")
    
    def test_market_robot_supply_endpoint(self):
        """GET /api/revenue/market-robot/all/supply works"""
        resp = requests.get(f"{BASE_URL}/api/revenue/market-robot/all/supply", headers=self.headers)
        assert resp.status_code == 200
        print("PASS: Supply endpoint works")
    
    def test_market_robot_logs_endpoint(self):
        """GET /api/revenue/market-robot/all/logs works"""
        resp = requests.get(f"{BASE_URL}/api/revenue/market-robot/all/logs", headers=self.headers)
        assert resp.status_code == 200
        print("PASS: Logs endpoint works")
    
    def test_market_robot_adjustments_endpoint(self):
        """GET /api/revenue/market-robot/all/adjustments works"""
        resp = requests.get(f"{BASE_URL}/api/revenue/market-robot/all/adjustments", headers=self.headers)
        assert resp.status_code == 200
        print("PASS: Adjustments endpoint works")
    
    def test_market_robot_competitors_endpoint(self):
        """GET /api/revenue/market-robot/all/competitors works"""
        resp = requests.get(f"{BASE_URL}/api/revenue/market-robot/all/competitors", headers=self.headers)
        assert resp.status_code == 200
        print("PASS: Competitors endpoint works")
    
    def test_market_robot_scanner_status_endpoint(self):
        """GET /api/revenue/market-robot/all/scanner/status works"""
        resp = requests.get(f"{BASE_URL}/api/revenue/market-robot/all/scanner/status", headers=self.headers)
        assert resp.status_code == 200
        print("PASS: Scanner status endpoint works")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
