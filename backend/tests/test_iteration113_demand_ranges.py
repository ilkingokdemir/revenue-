"""
Iteration 113 - Market Demand Dashboard: 8 Range Options + 3-Column ADR/Occupancy Comparison
Tests the new range selector (1/7/15/30/60/90/180/365 days) and 3-column comparison panel
(Our Hotel vs Market Average vs Competitors with ADR + Occupancy for each)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestDemandDashboardRanges:
    """Test all 8 day range options for demand-dashboard endpoint"""
    
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
    
    def test_range_1_day_today(self):
        """Test days=1 returns 1 day (Today)"""
        resp = requests.get(f"{BASE_URL}/api/revenue/market-robot/all/demand-dashboard?days=1", headers=self.headers)
        assert resp.status_code == 200, f"API failed: {resp.text}"
        data = resp.json()
        assert "daily_data" in data
        assert "kpis" in data
        assert len(data["daily_data"]) == 1, f"Expected 1 day, got {len(data['daily_data'])}"
        assert data["kpis"]["total_days"] == 1
        print(f"PASS: days=1 returns {len(data['daily_data'])} day(s)")
    
    def test_range_7_days(self):
        """Test days=7 returns 7 days"""
        resp = requests.get(f"{BASE_URL}/api/revenue/market-robot/all/demand-dashboard?days=7", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["daily_data"]) == 7, f"Expected 7 days, got {len(data['daily_data'])}"
        assert data["kpis"]["total_days"] == 7
        print(f"PASS: days=7 returns {len(data['daily_data'])} days")
    
    def test_range_15_days(self):
        """Test days=15 returns 15 days"""
        resp = requests.get(f"{BASE_URL}/api/revenue/market-robot/all/demand-dashboard?days=15", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["daily_data"]) == 15, f"Expected 15 days, got {len(data['daily_data'])}"
        assert data["kpis"]["total_days"] == 15
        print(f"PASS: days=15 returns {len(data['daily_data'])} days")
    
    def test_range_30_days(self):
        """Test days=30 returns 30 days"""
        resp = requests.get(f"{BASE_URL}/api/revenue/market-robot/all/demand-dashboard?days=30", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["daily_data"]) == 30, f"Expected 30 days, got {len(data['daily_data'])}"
        assert data["kpis"]["total_days"] == 30
        print(f"PASS: days=30 returns {len(data['daily_data'])} days")
    
    def test_range_60_days(self):
        """Test days=60 returns 60 days"""
        resp = requests.get(f"{BASE_URL}/api/revenue/market-robot/all/demand-dashboard?days=60", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["daily_data"]) == 60, f"Expected 60 days, got {len(data['daily_data'])}"
        assert data["kpis"]["total_days"] == 60
        print(f"PASS: days=60 returns {len(data['daily_data'])} days")
    
    def test_range_90_days(self):
        """Test days=90 returns 90 days"""
        resp = requests.get(f"{BASE_URL}/api/revenue/market-robot/all/demand-dashboard?days=90", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["daily_data"]) == 90, f"Expected 90 days, got {len(data['daily_data'])}"
        assert data["kpis"]["total_days"] == 90
        print(f"PASS: days=90 returns {len(data['daily_data'])} days")
    
    def test_range_180_days(self):
        """Test days=180 returns 180 days"""
        resp = requests.get(f"{BASE_URL}/api/revenue/market-robot/all/demand-dashboard?days=180", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["daily_data"]) == 180, f"Expected 180 days, got {len(data['daily_data'])}"
        assert data["kpis"]["total_days"] == 180
        print(f"PASS: days=180 returns {len(data['daily_data'])} days")
    
    def test_range_365_days(self):
        """Test days=365 returns 365 days (1 Year)"""
        resp = requests.get(f"{BASE_URL}/api/revenue/market-robot/all/demand-dashboard?days=365", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["daily_data"]) == 365, f"Expected 365 days, got {len(data['daily_data'])}"
        assert data["kpis"]["total_days"] == 365
        print(f"PASS: days=365 returns {len(data['daily_data'])} days")


class TestThreeColumnComparison:
    """Test 3-column ADR/Occupancy comparison KPIs: Our Hotel, Market Average, Competitors"""
    
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
    
    def test_our_hotel_kpis(self):
        """Test Our Hotel KPIs: our_adr and our_occupancy"""
        resp = requests.get(f"{BASE_URL}/api/revenue/market-robot/all/demand-dashboard?days=30", headers=self.headers)
        assert resp.status_code == 200
        kpis = resp.json()["kpis"]
        
        # Our Hotel ADR
        assert "our_adr" in kpis, "Missing our_adr in KPIs"
        assert isinstance(kpis["our_adr"], (int, float)), f"our_adr should be numeric, got {type(kpis['our_adr'])}"
        print(f"PASS: our_adr = {kpis['our_adr']}")
        
        # Our Hotel Occupancy
        assert "our_occupancy" in kpis, "Missing our_occupancy in KPIs"
        assert isinstance(kpis["our_occupancy"], (int, float)), f"our_occupancy should be numeric"
        assert 0 <= kpis["our_occupancy"] <= 100, f"our_occupancy should be 0-100, got {kpis['our_occupancy']}"
        print(f"PASS: our_occupancy = {kpis['our_occupancy']}%")
    
    def test_market_average_kpis(self):
        """Test Market Average KPIs: market_adr and market_occupancy"""
        resp = requests.get(f"{BASE_URL}/api/revenue/market-robot/all/demand-dashboard?days=30", headers=self.headers)
        assert resp.status_code == 200
        kpis = resp.json()["kpis"]
        
        # Market ADR (can be null if no supply data)
        assert "market_adr" in kpis, "Missing market_adr in KPIs"
        if kpis["market_adr"] is not None:
            assert isinstance(kpis["market_adr"], (int, float)), f"market_adr should be numeric or null"
        print(f"PASS: market_adr = {kpis['market_adr']}")
        
        # Market Occupancy (can be null if no supply data)
        assert "market_occupancy" in kpis, "Missing market_occupancy in KPIs"
        if kpis["market_occupancy"] is not None:
            assert isinstance(kpis["market_occupancy"], (int, float))
            assert 0 <= kpis["market_occupancy"] <= 100
        print(f"PASS: market_occupancy = {kpis['market_occupancy']}")
        
        # Market data days count
        assert "market_data_days" in kpis, "Missing market_data_days in KPIs"
        print(f"PASS: market_data_days = {kpis['market_data_days']}")
    
    def test_competitors_kpis(self):
        """Test Competitors KPIs: comp_adr, comp_occupancy, competitors_tracked"""
        resp = requests.get(f"{BASE_URL}/api/revenue/market-robot/all/demand-dashboard?days=30", headers=self.headers)
        assert resp.status_code == 200
        kpis = resp.json()["kpis"]
        
        # Competitor ADR (can be null if no competitor prices scraped)
        assert "comp_adr" in kpis, "Missing comp_adr in KPIs"
        if kpis["comp_adr"] is not None:
            assert isinstance(kpis["comp_adr"], (int, float))
        print(f"PASS: comp_adr = {kpis['comp_adr']}")
        
        # Competitor Occupancy (can be null if no competitor data)
        assert "comp_occupancy" in kpis, "Missing comp_occupancy in KPIs"
        if kpis["comp_occupancy"] is not None:
            assert isinstance(kpis["comp_occupancy"], (int, float))
        print(f"PASS: comp_occupancy = {kpis['comp_occupancy']}")
        
        # Competitors tracked count
        assert "competitors_tracked" in kpis, "Missing competitors_tracked in KPIs"
        assert isinstance(kpis["competitors_tracked"], int)
        print(f"PASS: competitors_tracked = {kpis['competitors_tracked']}")
    
    def test_all_six_kpis_present(self):
        """Verify all 6 ADR/Occupancy KPIs are present for 3-column comparison"""
        resp = requests.get(f"{BASE_URL}/api/revenue/market-robot/all/demand-dashboard?days=30", headers=self.headers)
        assert resp.status_code == 200
        kpis = resp.json()["kpis"]
        
        required_kpis = [
            "our_adr", "our_occupancy",           # Column 1: Our Hotel
            "market_adr", "market_occupancy",     # Column 2: Market Average
            "comp_adr", "comp_occupancy",         # Column 3: Competitors
            "market_data_days", "competitors_tracked"  # Supporting metrics
        ]
        
        for kpi in required_kpis:
            assert kpi in kpis, f"Missing required KPI: {kpi}"
        
        print(f"PASS: All 8 KPIs present for 3-column comparison")
        print(f"  Our Hotel: ADR={kpis['our_adr']}, Occ={kpis['our_occupancy']}%")
        print(f"  Market: ADR={kpis['market_adr']}, Occ={kpis['market_occupancy']}")
        print(f"  Competitors: ADR={kpis['comp_adr']}, Occ={kpis['comp_occupancy']}, Tracked={kpis['competitors_tracked']}")


class TestQuickStatsKPIs:
    """Test Quick Stats row KPIs: Above/Below/Aligned Market, High/Low Demand, Event Days, AI Managed, Days"""
    
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
    
    def test_quick_stats_kpis(self):
        """Test all 8 quick stats KPIs"""
        resp = requests.get(f"{BASE_URL}/api/revenue/market-robot/all/demand-dashboard?days=30", headers=self.headers)
        assert resp.status_code == 200
        kpis = resp.json()["kpis"]
        
        quick_stats = [
            ("above_market_days", "Above Market"),
            ("below_market_days", "Below Market"),
            ("aligned_days", "Aligned"),
            ("high_demand_days", "High Demand"),
            ("low_demand_days", "Low Demand"),
            ("event_days", "Event Days"),
            ("ai_managed_pct", "AI Managed %"),
            ("total_days", "Days"),
        ]
        
        for kpi_key, label in quick_stats:
            assert kpi_key in kpis, f"Missing quick stat KPI: {kpi_key} ({label})"
            assert isinstance(kpis[kpi_key], (int, float)), f"{kpi_key} should be numeric"
            print(f"PASS: {label} = {kpis[kpi_key]}")


class TestDailyDataFields:
    """Test daily_data entries have all required fields for Rate Grid table"""
    
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
    
    def test_daily_data_fields(self):
        """Test daily_data has all fields for Rate Grid: Date, Day, Status, Our ADR, Our Occ, Comp ADR, Position, Market, Floor, Event"""
        resp = requests.get(f"{BASE_URL}/api/revenue/market-robot/all/demand-dashboard?days=7", headers=self.headers)
        assert resp.status_code == 200
        daily_data = resp.json()["daily_data"]
        
        assert len(daily_data) > 0, "No daily_data returned"
        
        # Check first entry has all required fields
        entry = daily_data[0]
        required_fields = [
            "date",           # Date column
            "dow",            # Day column
            "ai_status",      # Status column
            "sell_rate",      # Our ADR column
            "occupancy",      # Our Occ column
            "comp_avg",       # Comp ADR column
            "position",       # Position column
            "position_pct",   # Position % value
            "market_unavail", # Market column
            "floor_rate",     # Floor column
            "event",          # Event column
        ]
        
        for field in required_fields:
            assert field in entry, f"Missing field in daily_data: {field}"
        
        print(f"PASS: All {len(required_fields)} fields present in daily_data")
        print(f"  Sample: date={entry['date']}, dow={entry['dow']}, sell_rate={entry['sell_rate']}, occupancy={entry['occupancy']}%")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
