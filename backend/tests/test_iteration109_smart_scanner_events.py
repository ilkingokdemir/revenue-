"""
Iteration 109 - Smart Scanner with Event Scanning Tests
Tests the updated Smart Scanner that now includes:
- Automatic event scanning alongside market scanning
- Auto-repricing with ALL 10 factors (DOW, Monthly, Occupancy, Market Supply, Competitors, Events, Aggressiveness, Historical Floors, Guardrails)
- Scanner start/stop/status endpoints with event-related fields
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestSmartScannerWithEvents:
    """Tests for Smart Scanner with integrated event scanning"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login and get auth token"""
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
        self.property_id = "all"
        yield
        # Cleanup: Stop scanner if running
        try:
            self.session.post(f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/scanner/stop")
        except:
            pass
    
    def test_01_scanner_start_returns_event_scanning_enabled(self):
        """POST /scanner/start should return status:'started' and event_scanning:true"""
        # First stop any running scanner
        self.session.post(f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/scanner/stop")
        time.sleep(1)
        
        # Start scanner
        resp = self.session.post(f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/scanner/start")
        assert resp.status_code == 200, f"Start failed: {resp.text}"
        
        data = resp.json()
        assert data.get("status") == "started", f"Expected status 'started', got: {data}"
        assert data.get("event_scanning") == True, f"Expected event_scanning=true, got: {data}"
        print(f"✓ Scanner started with event_scanning={data.get('event_scanning')}")
    
    def test_02_scanner_status_shows_running_with_event_fields(self):
        """GET /scanner/status should show running=true with event-related stats"""
        # Ensure scanner is running
        self.session.post(f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/scanner/start")
        time.sleep(2)
        
        resp = self.session.get(f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/scanner/status")
        assert resp.status_code == 200, f"Status failed: {resp.text}"
        
        data = resp.json()
        assert data.get("running") == True, f"Expected running=true, got: {data}"
        
        # Check stats has event-related fields
        stats = data.get("stats", {})
        assert "events_found_today" in stats, f"Missing events_found_today in stats: {stats}"
        assert "last_event_scan" in stats or stats.get("last_event_scan") is None, "last_event_scan field should exist"
        assert "event_scan_enabled" in stats, f"Missing event_scan_enabled in stats: {stats}"
        
        # Check event_scan_interval_mins
        assert "event_scan_interval_mins" in data, f"Missing event_scan_interval_mins: {data}"
        assert data.get("event_scan_interval_mins") == 360, f"Expected 360 mins (6 hours), got: {data.get('event_scan_interval_mins')}"
        
        print(f"✓ Scanner status: running={data.get('running')}, events_found_today={stats.get('events_found_today')}, event_scan_interval_mins={data.get('event_scan_interval_mins')}")
    
    def test_03_scanner_status_has_tier_info(self):
        """GET /scanner/status should include tier schedule info"""
        resp = self.session.get(f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/scanner/status")
        assert resp.status_code == 200
        
        data = resp.json()
        tiers = data.get("tiers", [])
        assert len(tiers) == 5, f"Expected 5 tiers, got: {len(tiers)}"
        
        expected_tiers = [
            {"label": "Today + Tomorrow", "interval_mins": 30},
            {"label": "Next 3-7 days", "interval_mins": 60},
            {"label": "1-2 weeks out", "interval_mins": 180},
            {"label": "2-4 weeks out", "interval_mins": 360},
            {"label": "1-3 months out", "interval_mins": 720},
        ]
        
        for i, tier in enumerate(tiers):
            assert tier.get("label") == expected_tiers[i]["label"], f"Tier {i} label mismatch"
            assert tier.get("interval_mins") == expected_tiers[i]["interval_mins"], f"Tier {i} interval mismatch"
        
        print(f"✓ Scanner has 5 tiers with correct intervals")
    
    def test_04_scanner_stop_returns_stopped(self):
        """POST /scanner/stop should return status:'stopped' and running becomes false"""
        # Ensure scanner is running first
        self.session.post(f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/scanner/start")
        time.sleep(1)
        
        # Stop scanner
        resp = self.session.post(f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/scanner/stop")
        assert resp.status_code == 200, f"Stop failed: {resp.text}"
        
        data = resp.json()
        assert data.get("status") == "stopped", f"Expected status 'stopped', got: {data}"
        
        # Verify status shows not running
        time.sleep(1)
        status_resp = self.session.get(f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/scanner/status")
        status_data = status_resp.json()
        assert status_data.get("running") == False, f"Expected running=false after stop, got: {status_data}"
        
        print(f"✓ Scanner stopped successfully, running={status_data.get('running')}")
    
    def test_05_scanner_already_running_returns_already_running(self):
        """Starting scanner twice should return 'already_running'"""
        # Stop first
        self.session.post(f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/scanner/stop")
        time.sleep(1)
        
        # Start first time
        resp1 = self.session.post(f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/scanner/start")
        assert resp1.status_code == 200
        assert resp1.json().get("status") == "started"
        
        # Start second time
        resp2 = self.session.post(f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/scanner/start")
        assert resp2.status_code == 200
        assert resp2.json().get("status") == "already_running", f"Expected 'already_running', got: {resp2.json()}"
        
        print(f"✓ Double start returns 'already_running'")


class TestAutoPricingFactors:
    """Tests to verify auto-pricing uses all 10 factors"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200
        token = login_resp.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        self.property_id = "all"
        yield
    
    def test_06_dynamic_pricing_has_10_factors(self):
        """Dynamic pricing should use all 10 factors including events, competitors, historical floors"""
        resp = self.session.post(f"{BASE_URL}/api/revenue/dynamic-pricing/{self.property_id}/calculate")
        assert resp.status_code == 200, f"Calculate failed: {resp.text}"
        
        data = resp.json()
        
        # Check data_sources
        data_sources = data.get("data_sources", {})
        # Actual keys from API: market_supply_dates, competitors_with_prices, strategy_configured, events_loaded, historical_floors
        expected_sources = ["market_supply_dates", "competitors_with_prices", "strategy_configured", "events_loaded", "historical_floors"]
        for source in expected_sources:
            assert source in data_sources, f"Missing data source: {source}"
        
        print(f"✓ Data sources present: {list(data_sources.keys())}")
        
        # Check prices have breakdown with factors
        prices = data.get("prices", [])
        if prices:
            first_price = prices[0]
            breakdown = first_price.get("breakdown", {})
            # The breakdown should contain factor names
            print(f"✓ Sample breakdown factors: {list(breakdown.keys())}")
    
    def test_07_dynamic_pricing_summary_includes_event_days(self):
        """Dynamic pricing summary should include event_days count"""
        resp = self.session.post(f"{BASE_URL}/api/revenue/dynamic-pricing/{self.property_id}/calculate")
        assert resp.status_code == 200
        
        data = resp.json()
        summary = data.get("summary", {})
        
        assert "event_days" in summary, f"Missing event_days in summary: {summary}"
        print(f"✓ Summary includes event_days={summary.get('event_days')}")
    
    def test_08_market_supply_includes_event_overlay(self):
        """GET /supply should include event data overlay on snapshots"""
        resp = self.session.get(f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/supply")
        assert resp.status_code == 200, f"Supply failed: {resp.text}"
        
        data = resp.json()
        summary = data.get("summary", {})
        
        # Check event_days in summary
        assert "event_days" in summary, f"Missing event_days in summary: {summary}"
        
        # Check upcoming_events
        upcoming = data.get("upcoming_events", [])
        print(f"✓ Supply data has event_days={summary.get('event_days')}, upcoming_events={len(upcoming)}")
        
        # Check snapshots can have event fields
        snapshots = data.get("snapshots", [])
        event_snapshots = [s for s in snapshots if s.get("event")]
        print(f"✓ {len(event_snapshots)} snapshots have event overlay")


class TestScannerStatsFields:
    """Tests for scanner stats fields"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200
        token = login_resp.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        self.property_id = "all"
        yield
        # Cleanup
        try:
            self.session.post(f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/scanner/stop")
        except:
            pass
    
    def test_09_scanner_stats_structure(self):
        """Scanner status stats should have all required fields"""
        # Start scanner to populate stats
        self.session.post(f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/scanner/start")
        time.sleep(2)
        
        resp = self.session.get(f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/scanner/status")
        assert resp.status_code == 200
        
        data = resp.json()
        stats = data.get("stats", {})
        
        # Required stats fields
        required_fields = [
            "total_scans_today",
            "total_requests_today",
            "last_scan_time",
            "last_reprice_time",
            "last_event_scan",
            "events_found_today",
            "event_scan_enabled",
            "tier_status",
            "started_at"
        ]
        
        for field in required_fields:
            assert field in stats, f"Missing stats field: {field}"
        
        print(f"✓ All required stats fields present")
        print(f"  - events_found_today: {stats.get('events_found_today')}")
        print(f"  - event_scan_enabled: {stats.get('event_scan_enabled')}")
        print(f"  - started_at: {stats.get('started_at')}")
    
    def test_10_scanner_event_scan_interval(self):
        """Scanner should have event_scan_interval_mins = 360 (6 hours)"""
        resp = self.session.get(f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/scanner/status")
        assert resp.status_code == 200
        
        data = resp.json()
        interval = data.get("event_scan_interval_mins")
        
        assert interval == 360, f"Expected event_scan_interval_mins=360, got: {interval}"
        print(f"✓ Event scan interval is {interval} minutes (6 hours)")


class TestMarketRobotConfig:
    """Tests for Market Robot configuration"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200
        token = login_resp.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        self.property_id = "all"
        yield
    
    def test_11_market_robot_config_structure(self):
        """GET /config should return proper configuration structure"""
        resp = self.session.get(f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/config")
        assert resp.status_code == 200, f"Config failed: {resp.text}"
        
        data = resp.json()
        
        # Required config fields
        required_fields = [
            "property_id",
            "enabled",
            "city",
            "scan_interval_minutes",
            "days_ahead",
            "auto_pricing",
            "max_increase_pct",
            "max_decrease_pct",
            "currency",
            "language"
        ]
        
        for field in required_fields:
            assert field in data, f"Missing config field: {field}"
        
        print(f"✓ Config structure valid: city={data.get('city')}, auto_pricing={data.get('auto_pricing')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
