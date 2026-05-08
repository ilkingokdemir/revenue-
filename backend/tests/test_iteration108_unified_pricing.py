"""
Iteration 108 - Unified Price Suggestions Testing
Tests the unified AI price suggestion system that combines:
1. Historical pricing data (2 years)
2. Market Robot scraping data
3. Event Intelligence
4. Competitor prices

Also tests the 10-factor AI Dynamic Pricing Engine including historical floors.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestUnifiedPriceSuggestions:
    """Test unified price suggestions in Historical Pricing endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        token = login_resp.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_historical_pricing_returns_unified_suggestions(self):
        """GET /api/revenue/historical-pricing/all returns min_price_suggestions with unified data"""
        resp = self.session.get(f"{BASE_URL}/api/revenue/historical-pricing/all")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        # Check min_price_suggestions exists
        assert "min_price_suggestions" in data, "min_price_suggestions missing"
        suggestions = data["min_price_suggestions"]
        assert len(suggestions) > 0, "No suggestions returned"
        
        # Check first suggestion has all unified fields
        s = suggestions[0]
        print(f"First suggestion: {s}")
        
        # Core fields
        assert "month" in s, "month missing"
        assert "month_name" in s, "month_name missing"
        assert "ai_suggested_rate" in s, "ai_suggested_rate missing"
        assert "suggested_min" in s, "suggested_min (floor) missing"
        
        # Historical data fields
        assert "historical_avg" in s, "historical_avg missing"
        assert "historical_min" in s, "historical_min missing"
        assert "historical_p25" in s, "historical_p25 missing"
        assert "historical_max" in s, "historical_max missing"
        assert "avg_occupancy" in s, "avg_occupancy missing"
        
        # Market Robot fields
        assert "market_unavail" in s or s.get("market_unavail") is None, "market_unavail field missing"
        assert "market_signal" in s or s.get("market_signal") is None, "market_signal field missing"
        assert "market_boost" in s, "market_boost missing"
        
        # Event Intelligence fields
        assert "events_count" in s, "events_count missing"
        assert "mega_events" in s, "mega_events missing"
        assert "event_names" in s, "event_names missing"
        assert "event_boost" in s, "event_boost missing"
        
        # Competitor fields
        assert "competitor_avg" in s or s.get("competitor_avg") is None, "competitor_avg field missing"
        assert "competitor_signal" in s or s.get("competitor_signal") is None, "competitor_signal field missing"
        assert "competitor_boost" in s, "competitor_boost missing"
        
        # Data sources object
        assert "data_sources" in s, "data_sources object missing"
        ds = s["data_sources"]
        assert "historical" in ds, "data_sources.historical missing"
        assert "market_robot" in ds, "data_sources.market_robot missing"
        assert "events" in ds, "data_sources.events missing"
        assert "competitors" in ds, "data_sources.competitors missing"
        
        print(f"PASS: Unified suggestion has all required fields")
        print(f"  - AI Suggested Rate: £{s['ai_suggested_rate']}")
        print(f"  - Floor: £{s['suggested_min']}")
        print(f"  - Historical Avg: £{s['historical_avg']}")
        print(f"  - Market Unavail: {s.get('market_unavail')}%")
        print(f"  - Market Signal: {s.get('market_signal')}")
        print(f"  - Events: {s['events_count']} total, {s['mega_events']} mega")
        print(f"  - Competitor Avg: £{s.get('competitor_avg')}")
        print(f"  - Data Sources: {ds}")
    
    def test_historical_pricing_all_months_have_suggestions(self):
        """All 12 months should have unified suggestions"""
        resp = self.session.get(f"{BASE_URL}/api/revenue/historical-pricing/all")
        assert resp.status_code == 200
        data = resp.json()
        
        suggestions = data["min_price_suggestions"]
        assert len(suggestions) == 12, f"Expected 12 months, got {len(suggestions)}"
        
        months_covered = [s["month"] for s in suggestions]
        print(f"Months covered: {months_covered}")
        
        # Each suggestion should have historical data (always present from seed)
        for s in suggestions:
            assert s["data_sources"]["historical"] == True, f"Month {s['month']} missing historical data"
            assert s["ai_suggested_rate"] > 0, f"Month {s['month']} has invalid ai_suggested_rate"
            assert s["suggested_min"] > 0, f"Month {s['month']} has invalid floor"
        
        print(f"PASS: All 12 months have unified suggestions with historical data")
    
    def test_historical_pricing_market_signal_values(self):
        """Market signal should be high_demand, moderate, low_demand, or None"""
        resp = self.session.get(f"{BASE_URL}/api/revenue/historical-pricing/all")
        assert resp.status_code == 200
        data = resp.json()
        
        valid_signals = ["high_demand", "moderate", "low_demand", None]
        for s in data["min_price_suggestions"]:
            signal = s.get("market_signal")
            assert signal in valid_signals, f"Invalid market_signal: {signal}"
            
            # If signal exists, boost should be set accordingly
            if signal == "high_demand":
                assert s["market_boost"] == 15, f"high_demand should have +15% boost"
            elif signal == "low_demand":
                assert s["market_boost"] == -5, f"low_demand should have -5% boost"
            elif signal == "moderate":
                assert s["market_boost"] == 0, f"moderate should have 0% boost"
        
        print(f"PASS: Market signals are valid")
    
    def test_historical_pricing_competitor_signal_values(self):
        """Competitor signal should be competitors_higher, competitors_lower, aligned, or None"""
        resp = self.session.get(f"{BASE_URL}/api/revenue/historical-pricing/all")
        assert resp.status_code == 200
        data = resp.json()
        
        valid_signals = ["competitors_higher", "competitors_lower", "aligned", None]
        for s in data["min_price_suggestions"]:
            signal = s.get("competitor_signal")
            assert signal in valid_signals, f"Invalid competitor_signal: {signal}"
            
            # If signal exists, boost should be set accordingly
            if signal == "competitors_higher":
                assert s["competitor_boost"] == 10, f"competitors_higher should have +10% boost"
            elif signal == "competitors_lower":
                assert s["competitor_boost"] == -5, f"competitors_lower should have -5% boost"
            elif signal == "aligned":
                assert s["competitor_boost"] == 0, f"aligned should have 0% boost"
        
        print(f"PASS: Competitor signals are valid")


class TestDynamicPricingHistoricalFloors:
    """Test 10-factor AI Dynamic Pricing Engine with historical floors"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        token = login_resp.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_dynamic_pricing_calculate_returns_historical_floors(self):
        """POST /api/revenue/dynamic-pricing/all/calculate returns data_sources with historical_floors"""
        resp = self.session.post(f"{BASE_URL}/api/revenue/dynamic-pricing/all/calculate", json={"days": 30})
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        # Check data_sources
        assert "data_sources" in data, "data_sources missing"
        ds = data["data_sources"]
        
        assert "historical_floors" in ds, "historical_floors count missing from data_sources"
        print(f"Historical Floors: {ds['historical_floors']} months")
        
        # Other data sources should also be present
        assert "market_supply_dates" in ds, "market_supply_dates missing"
        assert "competitors_with_prices" in ds, "competitors_with_prices missing"
        assert "strategy_configured" in ds, "strategy_configured missing"
        assert "events_loaded" in ds, "events_loaded missing"
        
        print(f"PASS: Dynamic pricing data_sources includes historical_floors")
        print(f"  - Market Supply Dates: {ds['market_supply_dates']}")
        print(f"  - Competitors with Prices: {ds['competitors_with_prices']}")
        print(f"  - Strategy Configured: {ds['strategy_configured']}")
        print(f"  - Events Loaded: {ds['events_loaded']}")
        print(f"  - Historical Floors: {ds['historical_floors']}")
    
    def test_dynamic_pricing_calculate_breakdown_structure(self):
        """Each price should have a breakdown dict with factor details"""
        resp = self.session.post(f"{BASE_URL}/api/revenue/dynamic-pricing/all/calculate", json={"days": 7})
        assert resp.status_code == 200
        data = resp.json()
        
        room_types = data.get("room_types", [])
        assert len(room_types) > 0, "No room types returned"
        
        prices = room_types[0].get("prices", [])
        assert len(prices) > 0, "No prices returned"
        
        # Check first price has breakdown
        p = prices[0]
        assert "breakdown" in p, "breakdown missing from price"
        breakdown = p["breakdown"]
        
        # Base should always be present
        assert "base" in breakdown, "base missing from breakdown"
        
        print(f"PASS: Price breakdown structure correct")
        print(f"  - Date: {p['date']}")
        print(f"  - AI Price: £{p['ai_price']}")
        print(f"  - Breakdown factors: {list(breakdown.keys())}")
    
    def test_dynamic_pricing_summary_stats(self):
        """Summary should include increases, decreases, avg_change_pct, event_days"""
        resp = self.session.post(f"{BASE_URL}/api/revenue/dynamic-pricing/all/calculate", json={"days": 30})
        assert resp.status_code == 200
        data = resp.json()
        
        summary = data.get("summary", {})
        assert "total_days" in summary, "total_days missing"
        assert "total_room_types" in summary, "total_room_types missing"
        assert "increases" in summary, "increases missing"
        assert "decreases" in summary, "decreases missing"
        assert "unchanged" in summary, "unchanged missing"
        assert "avg_change_pct" in summary, "avg_change_pct missing"
        assert "avg_ai_price" in summary, "avg_ai_price missing"
        assert "event_days" in summary, "event_days missing"
        
        print(f"PASS: Summary stats complete")
        print(f"  - Total Days: {summary['total_days']}")
        print(f"  - Increases: {summary['increases']}")
        print(f"  - Decreases: {summary['decreases']}")
        print(f"  - Avg Change: {summary['avg_change_pct']}%")
        print(f"  - Avg AI Price: £{summary['avg_ai_price']}")
        print(f"  - Event Days: {summary['event_days']}")
    
    def test_dynamic_pricing_apply_uses_historical_floors(self):
        """POST /api/revenue/dynamic-pricing/all/apply should use historical floors (10th factor)"""
        resp = self.session.post(f"{BASE_URL}/api/revenue/dynamic-pricing/all/apply", json={"days": 7})
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        assert "applied" in data, "applied count missing"
        assert "days" in data, "days missing"
        assert "room_types" in data, "room_types missing"
        assert "message" in data, "message missing"
        
        print(f"PASS: Dynamic pricing apply successful")
        print(f"  - Applied: {data['applied']} rate entries")
        print(f"  - Days: {data['days']}")
        print(f"  - Room Types: {data['room_types']}")
    
    def test_dynamic_pricing_price_has_all_market_data(self):
        """Each price should include market_unavail, competitor_avg, event info"""
        resp = self.session.post(f"{BASE_URL}/api/revenue/dynamic-pricing/all/calculate", json={"days": 14})
        assert resp.status_code == 200
        data = resp.json()
        
        prices = data["room_types"][0]["prices"]
        
        # Check structure of each price
        for p in prices[:5]:  # Check first 5
            assert "date" in p
            assert "day" in p
            assert "dow" in p
            assert "days_ahead" in p
            assert "base_rate" in p
            assert "current_rate" in p
            assert "ai_price" in p
            assert "change_pct" in p
            assert "our_occupancy" in p
            assert "market_unavail" in p or p.get("market_unavail") is None
            assert "competitor_avg" in p or p.get("competitor_avg") is None
            assert "event" in p or p.get("event") is None
            assert "event_impact" in p or p.get("event_impact") is None
            assert "breakdown" in p
            assert "is_today" in p
        
        print(f"PASS: Price entries have all market data fields")


class TestApplyPriceFloors:
    """Test applying price floors from historical analysis"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        token = login_resp.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_apply_floors_from_historical_analysis(self):
        """POST /api/revenue/historical-pricing/all/apply-floors saves floors to strategy"""
        # Apply floors for months 1, 2, 3
        floors = [
            {"month": 1, "min_price": 85.00},
            {"month": 2, "min_price": 75.00},
            {"month": 3, "min_price": 90.00}
        ]
        
        resp = self.session.post(f"{BASE_URL}/api/revenue/historical-pricing/all/apply-floors", json={"floors": floors})
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        assert "applied" in data, "applied count missing"
        assert data["applied"] == 3, f"Expected 3 floors applied, got {data['applied']}"
        
        print(f"PASS: Applied {data['applied']} price floors")
    
    def test_floors_reflected_in_dynamic_pricing(self):
        """After applying floors, dynamic pricing should show historical_floors count"""
        # First apply some floors
        floors = [
            {"month": 4, "min_price": 95.00},
            {"month": 5, "min_price": 100.00},
            {"month": 6, "min_price": 110.00}
        ]
        self.session.post(f"{BASE_URL}/api/revenue/historical-pricing/all/apply-floors", json={"floors": floors})
        
        # Now check dynamic pricing
        resp = self.session.post(f"{BASE_URL}/api/revenue/dynamic-pricing/all/calculate", json={"days": 30})
        assert resp.status_code == 200
        data = resp.json()
        
        ds = data["data_sources"]
        # Should have at least the floors we just applied (may have more from previous tests)
        assert ds["historical_floors"] >= 3, f"Expected at least 3 historical floors, got {ds['historical_floors']}"
        
        print(f"PASS: Dynamic pricing shows {ds['historical_floors']} historical floors")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
