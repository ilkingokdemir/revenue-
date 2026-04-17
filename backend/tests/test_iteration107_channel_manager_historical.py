"""
Iteration 107 - Channel Manager & Historical Pricing Analysis Tests
Tests the NEW Channel Manager (9 OTA channels, rate push, preview, logs) and
Historical Pricing Analysis (2yr data, monthly/DOW/season stats, AI min price suggestions)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuth:
    """Authentication for testing"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Login and get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, f"No token in response: {data}"
        return data["token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestChannelManager(TestAuth):
    """Channel Manager API Tests - 9 OTA channels, rate push, preview, logs"""
    
    def test_get_channels_returns_9_channels(self, auth_headers):
        """GET /api/revenue/channel-manager/all returns 9 channels with summary"""
        response = requests.get(f"{BASE_URL}/api/revenue/channel-manager/all", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify channels array
        assert "channels" in data
        channels = data["channels"]
        assert len(channels) == 9, f"Expected 9 channels, got {len(channels)}"
        
        # Verify expected channel IDs
        channel_ids = [c["channel_id"] for c in channels]
        expected_ids = ["booking_com", "expedia", "airbnb", "hotels_com", "agoda", 
                       "trip_com", "google_hotels", "trivago", "direct"]
        for eid in expected_ids:
            assert eid in channel_ids, f"Missing channel: {eid}"
        
        # Verify summary
        assert "summary" in data
        summary = data["summary"]
        assert "total_channels" in summary
        assert summary["total_channels"] == 9
        assert "connected" in summary
        assert "disconnected" in summary
        assert "auto_syncing" in summary
        
        # Direct Website should be auto-connected
        direct = next((c for c in channels if c["channel_id"] == "direct"), None)
        assert direct is not None
        assert direct["connected"] == True
        print(f"✓ 9 channels returned: {channel_ids}")
        print(f"✓ Summary: {summary['connected']} connected, {summary['disconnected']} disconnected")
    
    def test_channel_has_required_fields(self, auth_headers):
        """Verify each channel has required fields"""
        response = requests.get(f"{BASE_URL}/api/revenue/channel-manager/all", headers=auth_headers)
        assert response.status_code == 200
        channels = response.json()["channels"]
        
        required_fields = ["channel_id", "name", "type", "color", "commission_pct", 
                         "connected", "status", "rate_rule", "auto_sync"]
        
        for ch in channels:
            for field in required_fields:
                assert field in ch, f"Channel {ch.get('name', 'unknown')} missing field: {field}"
        
        print(f"✓ All 9 channels have required fields")
    
    def test_connect_channel_expedia(self, auth_headers):
        """PUT /api/revenue/channel-manager/all/expedia connects channel"""
        response = requests.put(
            f"{BASE_URL}/api/revenue/channel-manager/all/expedia",
            headers=auth_headers,
            json={"connected": True}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "message" in data
        assert data["channel_id"] == "expedia"
        
        # Verify connection
        verify = requests.get(f"{BASE_URL}/api/revenue/channel-manager/all", headers=auth_headers)
        channels = verify.json()["channels"]
        expedia = next((c for c in channels if c["channel_id"] == "expedia"), None)
        assert expedia is not None
        assert expedia["connected"] == True
        assert expedia["status"] == "active"
        print(f"✓ Expedia connected successfully")
    
    def test_update_channel_rate_rule(self, auth_headers):
        """PUT /api/revenue/channel-manager/all/expedia updates rate rule"""
        response = requests.put(
            f"{BASE_URL}/api/revenue/channel-manager/all/expedia",
            headers=auth_headers,
            json={"rate_rule": "markup", "rate_markup_pct": 5}
        )
        assert response.status_code == 200
        
        # Verify update
        verify = requests.get(f"{BASE_URL}/api/revenue/channel-manager/all", headers=auth_headers)
        channels = verify.json()["channels"]
        expedia = next((c for c in channels if c["channel_id"] == "expedia"), None)
        assert expedia["rate_rule"] == "markup"
        assert expedia["rate_markup_pct"] == 5
        print(f"✓ Expedia rate rule updated to markup +5%")
    
    def test_push_rates_to_connected_channels(self, auth_headers):
        """POST /api/revenue/channel-manager/all/push-rates pushes rates"""
        response = requests.post(
            f"{BASE_URL}/api/revenue/channel-manager/all/push-rates",
            headers=auth_headers,
            json={"days": 7}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "message" in data
        assert "channels_pushed" in data
        assert data["channels_pushed"] >= 1  # At least Direct + Expedia
        assert "total_rates" in data
        assert "results" in data
        
        # Verify results per channel
        for result in data["results"]:
            assert "channel" in result
            assert "rates_pushed" in result
            assert "rule" in result
        
        print(f"✓ Rates pushed to {data['channels_pushed']} channels ({data['total_rates']} rate entries)")
    
    def test_rate_preview_7_days(self, auth_headers):
        """GET /api/revenue/channel-manager/all/rate-preview?days=7 returns preview"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/channel-manager/all/rate-preview?days=7",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "preview" in data
        assert "channels" in data
        
        preview = data["preview"]
        assert len(preview) == 7, f"Expected 7 days, got {len(preview)}"
        
        # Verify each day has required fields
        for day in preview:
            assert "date" in day
            assert "dow" in day
            assert "our_rate" in day
        
        print(f"✓ Rate preview returned for 7 days")
        print(f"  Sample: {preview[0]['date']} ({preview[0]['dow']}) - Our rate: £{preview[0]['our_rate']}")
    
    def test_push_logs_returns_history(self, auth_headers):
        """GET /api/revenue/channel-manager/all/push-logs returns push history"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/channel-manager/all/push-logs",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "logs" in data
        logs = data["logs"]
        assert len(logs) >= 1, "Expected at least 1 push log after push-rates test"
        
        # Verify log structure
        log = logs[0]
        assert "channel_id" in log
        assert "channel_name" in log
        assert "rates_pushed" in log
        assert "rule" in log
        assert "pushed_at" in log
        
        print(f"✓ Push logs returned: {len(logs)} entries")
    
    def test_disconnect_channel(self, auth_headers):
        """PUT /api/revenue/channel-manager/all/expedia disconnects channel"""
        response = requests.put(
            f"{BASE_URL}/api/revenue/channel-manager/all/expedia",
            headers=auth_headers,
            json={"connected": False}
        )
        assert response.status_code == 200
        
        # Verify disconnection
        verify = requests.get(f"{BASE_URL}/api/revenue/channel-manager/all", headers=auth_headers)
        channels = verify.json()["channels"]
        expedia = next((c for c in channels if c["channel_id"] == "expedia"), None)
        assert expedia["connected"] == False
        assert expedia["status"] == "disconnected"
        print(f"✓ Expedia disconnected successfully")


class TestHistoricalPricing(TestAuth):
    """Historical Pricing Analysis API Tests - 2yr data, stats, AI suggestions"""
    
    def test_get_historical_analysis_returns_730_days(self, auth_headers):
        """GET /api/revenue/historical-pricing/all returns 730 days data"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/historical-pricing/all",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify KPIs
        assert "kpis" in data
        kpis = data["kpis"]
        assert kpis["total_data_points"] >= 700, f"Expected ~730 days, got {kpis['total_data_points']}"
        assert "date_range" in kpis
        assert "overall_avg_rate" in kpis
        assert "overall_min_rate" in kpis
        assert "overall_max_rate" in kpis
        assert "year1_avg" in kpis
        assert "year2_avg" in kpis
        assert "yoy_change_pct" in kpis
        
        print(f"✓ Historical data: {kpis['total_data_points']} days analyzed")
        print(f"  Date range: {kpis['date_range']}")
        print(f"  2yr avg rate: £{kpis['overall_avg_rate']}")
    
    def test_monthly_stats_12_months(self, auth_headers):
        """Verify monthly_stats has 12 months"""
        response = requests.get(f"{BASE_URL}/api/revenue/historical-pricing/all", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "monthly_stats" in data
        monthly_stats = data["monthly_stats"]
        assert len(monthly_stats) == 12, f"Expected 12 months, got {len(monthly_stats)}"
        
        # Verify each month has required fields
        required = ["month", "month_name", "avg_rate", "min_rate", "max_rate", 
                   "median_rate", "p25_rate", "avg_occupancy", "total_revenue"]
        for ms in monthly_stats:
            for field in required:
                assert field in ms, f"Month {ms.get('month_name', '?')} missing: {field}"
        
        print(f"✓ Monthly stats: 12 months with all required fields")
    
    def test_dow_stats_7_days(self, auth_headers):
        """Verify dow_stats has 7 days"""
        response = requests.get(f"{BASE_URL}/api/revenue/historical-pricing/all", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "dow_stats" in data
        dow_stats = data["dow_stats"]
        assert len(dow_stats) == 7, f"Expected 7 days, got {len(dow_stats)}"
        
        # Verify each day has required fields
        for ds in dow_stats:
            assert "dow" in ds
            assert "dow_name" in ds
            assert "avg_rate" in ds
            assert "min_rate" in ds
            assert "max_rate" in ds
        
        print(f"✓ DOW stats: 7 days (Mon-Sun)")
    
    def test_season_stats_4_seasons(self, auth_headers):
        """Verify season_stats has 4 seasons"""
        response = requests.get(f"{BASE_URL}/api/revenue/historical-pricing/all", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "season_stats" in data
        season_stats = data["season_stats"]
        
        expected_seasons = ["peak", "holiday", "shoulder", "low"]
        for season in expected_seasons:
            assert season in season_stats, f"Missing season: {season}"
            ss = season_stats[season]
            assert "avg_rate" in ss
            assert "min_rate" in ss
            assert "max_rate" in ss
            assert "avg_occupancy" in ss
        
        print(f"✓ Season stats: {list(season_stats.keys())}")
    
    def test_min_price_suggestions_12_months(self, auth_headers):
        """Verify min_price_suggestions has 12 months with AI reasoning"""
        response = requests.get(f"{BASE_URL}/api/revenue/historical-pricing/all", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "min_price_suggestions" in data
        suggestions = data["min_price_suggestions"]
        assert len(suggestions) == 12, f"Expected 12 suggestions, got {len(suggestions)}"
        
        # Verify each suggestion has required fields
        required = ["month", "month_name", "suggested_min", "historical_avg", 
                   "historical_min", "historical_p25", "historical_max", "reasoning"]
        for s in suggestions:
            for field in required:
                assert field in s, f"Suggestion for month {s.get('month', '?')} missing: {field}"
            # Verify reasoning is meaningful
            assert len(s["reasoning"]) > 20, "Reasoning should be descriptive"
        
        print(f"✓ AI min price suggestions: 12 months")
        print(f"  Sample: {suggestions[0]['month_name']} - Suggested min: £{suggestions[0]['suggested_min']}")
    
    def test_apply_price_floors(self, auth_headers):
        """POST /api/revenue/historical-pricing/all/apply-floors saves floors"""
        # First get suggestions
        response = requests.get(f"{BASE_URL}/api/revenue/historical-pricing/all", headers=auth_headers)
        suggestions = response.json()["min_price_suggestions"]
        
        # Apply first 3 months as floors
        floors = [{"month": s["month"], "min_price": s["suggested_min"]} for s in suggestions[:3]]
        
        response = requests.post(
            f"{BASE_URL}/api/revenue/historical-pricing/all/apply-floors",
            headers=auth_headers,
            json={"floors": floors}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "message" in data
        assert "applied" in data
        assert data["applied"] == 3
        
        print(f"✓ Applied {data['applied']} monthly price floors")
    
    def test_yoy_comparison_data(self, auth_headers):
        """Verify year-over-year comparison data"""
        response = requests.get(f"{BASE_URL}/api/revenue/historical-pricing/all", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        kpis = data["kpis"]
        
        # Verify YoY fields
        assert "year1_avg" in kpis
        assert "year2_avg" in kpis
        assert "yoy_change_pct" in kpis
        assert "year1_revenue" in kpis
        assert "year2_revenue" in kpis
        assert "year1_avg_occ" in kpis
        assert "year2_avg_occ" in kpis
        
        # YoY change should be a reasonable percentage
        assert -100 <= kpis["yoy_change_pct"] <= 100
        
        print(f"✓ YoY comparison: Year1 avg £{kpis['year1_avg']} vs Year2 avg £{kpis['year2_avg']}")
        print(f"  YoY change: {kpis['yoy_change_pct']}%")


class TestRevenueSidebarNavigation(TestAuth):
    """Verify Revenue sidebar has Channel Manager and Historical Analysis"""
    
    def test_channel_manager_endpoint_accessible(self, auth_headers):
        """Channel Manager endpoint is accessible"""
        response = requests.get(f"{BASE_URL}/api/revenue/channel-manager/all", headers=auth_headers)
        assert response.status_code == 200
        print("✓ Channel Manager endpoint accessible")
    
    def test_historical_pricing_endpoint_accessible(self, auth_headers):
        """Historical Pricing endpoint is accessible"""
        response = requests.get(f"{BASE_URL}/api/revenue/historical-pricing/all", headers=auth_headers)
        assert response.status_code == 200
        print("✓ Historical Pricing endpoint accessible")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
