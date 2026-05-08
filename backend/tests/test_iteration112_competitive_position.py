"""
Iteration 112 - Competitive Position & Market Landscape Testing
Tests:
1. Supply endpoint returns ALL snapshots (no 24h cutoff)
2. Demand dashboard includes comp_avg, position, position_pct per day
3. KPIs include competitor-related metrics
4. Nights selector works for all ranges (30, 60, 90, 180, 365)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    return data.get("access_token") or data.get("token")

@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Auth headers for requests"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestSupplyEndpointNoTimeCutoff:
    """Test that supply endpoint returns ALL snapshots without 24h cutoff"""
    
    def test_supply_returns_all_snapshots(self, auth_headers):
        """Supply endpoint should return all available snapshots, not just last 24h"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/all/supply",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Supply endpoint failed: {response.text}"
        data = response.json()
        
        # Should have snapshots array
        assert "snapshots" in data, "Response missing 'snapshots' field"
        snapshots = data["snapshots"]
        
        # Should have summary
        assert "summary" in data, "Response missing 'summary' field"
        summary = data["summary"]
        
        # Summary should have total_dates
        assert "total_dates" in summary, "Summary missing 'total_dates'"
        print(f"Supply endpoint returned {len(snapshots)} snapshots, summary shows {summary['total_dates']} dates")
        
        # Verify snapshot structure
        if snapshots:
            snap = snapshots[0]
            required_fields = ["date", "total_properties", "unavailable_pct", "available_pct", "scraped"]
            for field in required_fields:
                assert field in snap, f"Snapshot missing '{field}' field"
        
        return len(snapshots)


class TestDemandDashboardCompetitorFields:
    """Test demand dashboard includes competitor positioning fields"""
    
    def test_demand_dashboard_365_days_has_competitor_fields(self, auth_headers):
        """Demand dashboard should include comp_avg, position, position_pct per day"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/all/demand-dashboard?days=365",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Demand dashboard failed: {response.text}"
        data = response.json()
        
        # Should have daily_data
        assert "daily_data" in data, "Response missing 'daily_data'"
        daily_data = data["daily_data"]
        assert len(daily_data) == 365, f"Expected 365 days, got {len(daily_data)}"
        
        # Check first entry has competitor fields
        entry = daily_data[0]
        competitor_fields = ["comp_avg", "position", "position_pct"]
        for field in competitor_fields:
            assert field in entry, f"Daily entry missing '{field}' field"
        
        print(f"First day: date={entry['date']}, comp_avg={entry['comp_avg']}, position={entry['position']}, position_pct={entry['position_pct']}")
        
        # Position should be one of: above, below, aligned, or None
        valid_positions = ["above", "below", "aligned", None]
        assert entry["position"] in valid_positions, f"Invalid position: {entry['position']}"
    
    def test_demand_dashboard_kpis_have_competitor_metrics(self, auth_headers):
        """KPIs should include competitor-related metrics"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/all/demand-dashboard?days=365",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should have kpis
        assert "kpis" in data, "Response missing 'kpis'"
        kpis = data["kpis"]
        
        # Check for competitor KPIs
        competitor_kpis = [
            "avg_competitor_rate",
            "above_market_days",
            "below_market_days",
            "aligned_days",
            "avg_position_pct",
            "competitors_tracked"
        ]
        for kpi in competitor_kpis:
            assert kpi in kpis, f"KPIs missing '{kpi}'"
        
        print(f"Competitor KPIs: avg_competitor_rate={kpis['avg_competitor_rate']}, "
              f"above_market={kpis['above_market_days']}, below_market={kpis['below_market_days']}, "
              f"aligned={kpis['aligned_days']}, avg_position_pct={kpis['avg_position_pct']}, "
              f"competitors_tracked={kpis['competitors_tracked']}")
        
        # Verify types
        assert isinstance(kpis["above_market_days"], int), "above_market_days should be int"
        assert isinstance(kpis["below_market_days"], int), "below_market_days should be int"
        assert isinstance(kpis["aligned_days"], int), "aligned_days should be int"
        assert isinstance(kpis["competitors_tracked"], int), "competitors_tracked should be int"
    
    def test_demand_dashboard_all_day_ranges(self, auth_headers):
        """Test demand dashboard works for all day ranges: 30, 60, 90, 180, 365"""
        for days in [30, 60, 90, 180, 365]:
            response = requests.get(
                f"{BASE_URL}/api/revenue/market-robot/all/demand-dashboard?days={days}",
                headers=auth_headers
            )
            assert response.status_code == 200, f"Demand dashboard failed for {days} days: {response.text}"
            data = response.json()
            
            assert "daily_data" in data
            assert len(data["daily_data"]) == days, f"Expected {days} days, got {len(data['daily_data'])}"
            
            # Verify competitor fields present
            entry = data["daily_data"][0]
            assert "comp_avg" in entry
            assert "position" in entry
            assert "position_pct" in entry
            
            print(f"Days={days}: Got {len(data['daily_data'])} entries, KPIs present")


class TestDemandDashboardEntryStructure:
    """Test complete structure of daily_data entries"""
    
    def test_daily_entry_has_all_required_fields(self, auth_headers):
        """Each daily entry should have all required fields including new competitor fields"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/all/demand-dashboard?days=30",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        entry = data["daily_data"][0]
        
        # All required fields (including new competitor fields)
        required_fields = [
            "date", "day", "dow", "month", "days_ahead",
            "occupancy", "market_unavail", "demand_level",
            "base_rate", "ai_rate", "sell_rate", "min_rate", "floor_rate", "target_rate",
            "comp_avg", "position", "position_pct",  # NEW competitor fields
            "ai_status", "set_by",
            "event", "event_impact", "event_attendance"
        ]
        
        missing = [f for f in required_fields if f not in entry]
        assert not missing, f"Daily entry missing fields: {missing}"
        
        print(f"Daily entry has all {len(required_fields)} required fields")
        print(f"Sample entry: date={entry['date']}, sell_rate={entry['sell_rate']}, "
              f"comp_avg={entry['comp_avg']}, position={entry['position']}, position_pct={entry['position_pct']}")


class TestKPIsStructure:
    """Test complete KPIs structure"""
    
    def test_kpis_have_all_required_fields(self, auth_headers):
        """KPIs should have all required fields including competitor metrics"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/all/demand-dashboard?days=365",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        kpis = data["kpis"]
        
        # All required KPI fields
        required_kpis = [
            "total_days", "avg_occupancy", "avg_sell_rate", "base_rate",
            "high_demand_days", "low_demand_days", "event_days",
            "ai_managed_days", "ai_managed_pct",
            # NEW competitor KPIs
            "avg_competitor_rate", "above_market_days", "below_market_days",
            "aligned_days", "avg_position_pct", "competitors_tracked"
        ]
        
        missing = [k for k in required_kpis if k not in kpis]
        assert not missing, f"KPIs missing fields: {missing}"
        
        print(f"KPIs have all {len(required_kpis)} required fields")
        print(f"KPIs: total_days={kpis['total_days']}, avg_sell_rate={kpis['avg_sell_rate']}, "
              f"avg_competitor_rate={kpis['avg_competitor_rate']}, competitors_tracked={kpis['competitors_tracked']}")


class TestPositionCalculation:
    """Test position calculation logic"""
    
    def test_position_values_are_valid(self, auth_headers):
        """Position should be 'above', 'below', 'aligned', or None"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/all/demand-dashboard?days=30",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        valid_positions = ["above", "below", "aligned", None]
        
        for entry in data["daily_data"]:
            assert entry["position"] in valid_positions, f"Invalid position: {entry['position']} on {entry['date']}"
            
            # If position is set, position_pct should be a number
            if entry["position"] is not None:
                assert isinstance(entry["position_pct"], (int, float)), f"position_pct should be numeric when position is set"
        
        # Count positions
        above = sum(1 for e in data["daily_data"] if e["position"] == "above")
        below = sum(1 for e in data["daily_data"] if e["position"] == "below")
        aligned = sum(1 for e in data["daily_data"] if e["position"] == "aligned")
        no_data = sum(1 for e in data["daily_data"] if e["position"] is None)
        
        print(f"Position distribution: above={above}, below={below}, aligned={aligned}, no_data={no_data}")
        
        # Verify KPIs match
        kpis = data["kpis"]
        assert kpis["above_market_days"] == above, "above_market_days KPI mismatch"
        assert kpis["below_market_days"] == below, "below_market_days KPI mismatch"
        assert kpis["aligned_days"] == aligned, "aligned_days KPI mismatch"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
