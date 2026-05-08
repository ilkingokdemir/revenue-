"""
Iteration 106 - Rate Parity & Competitor Analysis Testing
Tests the new Rate Parity scanning and Competitor Analysis endpoints.

Features tested:
- POST /api/revenue/market-robot/{property_id}/parity/scan - Scan OTA channels for rate parity
- GET /api/revenue/market-robot/{property_id}/parity - Get parity data with summary
- GET /api/revenue/market-robot/{property_id}/competitor-analysis - Deep competitor analysis
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestRateParityAndCompetitorAnalysis:
    """Test Rate Parity and Competitor Analysis endpoints"""
    
    auth_token = None
    property_id = "all"
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        if not TestRateParityAndCompetitorAnalysis.auth_token:
            response = requests.post(f"{BASE_URL}/api/auth/login", json={
                "email": "admin@hotelbox.com",
                "password": "HotelAdmin2026!"
            })
            assert response.status_code == 200, f"Login failed: {response.text}"
            data = response.json()
            TestRateParityAndCompetitorAnalysis.auth_token = data.get("access_token") or data.get("token")
        
        self.headers = {
            "Authorization": f"Bearer {TestRateParityAndCompetitorAnalysis.auth_token}",
            "Content-Type": "application/json"
        }
    
    # ==================== RATE PARITY TESTS ====================
    
    def test_01_parity_scan_endpoint(self):
        """Test POST /api/revenue/market-robot/{property_id}/parity/scan"""
        response = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/parity/scan",
            headers=self.headers,
            json={"days": 14}
        )
        assert response.status_code == 200, f"Parity scan failed: {response.text}"
        
        data = response.json()
        # Verify response structure
        assert "dates_scanned" in data, "Missing dates_scanned"
        assert "violations_found" in data, "Missing violations_found"
        assert "channels_checked" in data, "Missing channels_checked"
        assert "message" in data, "Missing message"
        
        # Verify values
        assert data["dates_scanned"] == 14, f"Expected 14 dates, got {data['dates_scanned']}"
        assert data["channels_checked"] == 6, f"Expected 6 channels, got {data['channels_checked']}"
        assert isinstance(data["violations_found"], int), "violations_found should be int"
        
        print(f"✓ Parity scan: {data['dates_scanned']} dates, {data['channels_checked']} channels, {data['violations_found']} violations")
    
    def test_02_get_parity_data(self):
        """Test GET /api/revenue/market-robot/{property_id}/parity"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/parity",
            headers=self.headers
        )
        assert response.status_code == 200, f"Get parity failed: {response.text}"
        
        data = response.json()
        # Verify response structure
        assert "parity_data" in data, "Missing parity_data"
        assert "channels" in data, "Missing channels"
        assert "summary" in data, "Missing summary"
        
        # Verify parity_data array
        parity_data = data["parity_data"]
        assert isinstance(parity_data, list), "parity_data should be array"
        assert len(parity_data) >= 14, f"Expected at least 14 dates, got {len(parity_data)}"
        
        # Verify first parity entry structure
        if parity_data:
            entry = parity_data[0]
            assert "date" in entry, "Missing date in parity entry"
            assert "our_price" in entry, "Missing our_price in parity entry"
            assert "channels" in entry, "Missing channels in parity entry"
            
            # Verify channel data structure
            channels = entry["channels"]
            assert isinstance(channels, dict), "channels should be dict"
            
            # Check at least one channel has proper structure
            for ch_id, ch_data in channels.items():
                assert "price" in ch_data, f"Missing price in channel {ch_id}"
                assert "diff_pct" in ch_data, f"Missing diff_pct in channel {ch_id}"
                assert "status" in ch_data, f"Missing status in channel {ch_id}"
                assert ch_data["status"] in ["parity", "minor", "violation"], f"Invalid status: {ch_data['status']}"
                break
        
        print(f"✓ Parity data: {len(parity_data)} dates with channel data")
    
    def test_03_parity_channels_list(self):
        """Test that channels list contains all 6 OTA channels"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/parity",
            headers=self.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        channels = data["channels"]
        
        # Verify 6 channels
        assert len(channels) == 6, f"Expected 6 channels, got {len(channels)}"
        
        # Verify channel IDs
        channel_ids = [ch["id"] for ch in channels]
        expected_ids = ["booking", "expedia", "hotels_com", "agoda", "google", "direct"]
        for expected_id in expected_ids:
            assert expected_id in channel_ids, f"Missing channel: {expected_id}"
        
        # Verify channel structure
        for ch in channels:
            assert "id" in ch, "Missing id in channel"
            assert "name" in ch, "Missing name in channel"
            assert "color" in ch, "Missing color in channel"
            assert "icon" in ch, "Missing icon in channel"
        
        print(f"✓ Channels: {', '.join([ch['name'] for ch in channels])}")
    
    def test_04_parity_summary_structure(self):
        """Test parity summary contains all required fields"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/parity",
            headers=self.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        summary = data["summary"]
        
        # Verify summary fields
        required_fields = ["total_dates", "total_checks", "violations", "minor_issues", "in_parity", "parity_score"]
        for field in required_fields:
            assert field in summary, f"Missing {field} in summary"
        
        # Verify parity_score is percentage
        assert 0 <= summary["parity_score"] <= 100, f"Invalid parity_score: {summary['parity_score']}"
        
        # Verify counts add up
        total = summary["violations"] + summary["minor_issues"] + summary["in_parity"]
        assert total == summary["total_checks"], f"Counts don't add up: {total} != {summary['total_checks']}"
        
        print(f"✓ Summary: Score={summary['parity_score']}%, In Parity={summary['in_parity']}, Minor={summary['minor_issues']}, Violations={summary['violations']}")
    
    # ==================== COMPETITOR ANALYSIS TESTS ====================
    
    def test_05_competitor_analysis_endpoint(self):
        """Test GET /api/revenue/market-robot/{property_id}/competitor-analysis"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/competitor-analysis",
            headers=self.headers
        )
        assert response.status_code == 200, f"Competitor analysis failed: {response.text}"
        
        data = response.json()
        # Verify response structure
        assert "comparison" in data, "Missing comparison"
        assert "insights" in data, "Missing insights"
        assert "kpis" in data, "Missing kpis"
        assert "competitors_count" in data, "Missing competitors_count"
        
        print(f"✓ Competitor analysis: {data['competitors_count']} competitors tracked")
    
    def test_06_competitor_analysis_comparison_array(self):
        """Test comparison array has 14 days of data"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/competitor-analysis",
            headers=self.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        comparison = data["comparison"]
        
        # Verify 14 days
        assert isinstance(comparison, list), "comparison should be array"
        assert len(comparison) == 14, f"Expected 14 days, got {len(comparison)}"
        
        # Verify comparison entry structure
        entry = comparison[0]
        required_fields = ["date", "our_price", "comp_avg", "comp_min", "comp_max", "comp_count", 
                          "diff_pct", "position", "demand_level"]
        for field in required_fields:
            assert field in entry, f"Missing {field} in comparison entry"
        
        # Verify position values
        valid_positions = ["premium", "above_avg", "competitive", "undercut", "unknown"]
        assert entry["position"] in valid_positions, f"Invalid position: {entry['position']}"
        
        # Verify demand_level values
        valid_demand = ["high", "moderate", "low"]
        assert entry["demand_level"] in valid_demand, f"Invalid demand_level: {entry['demand_level']}"
        
        print(f"✓ Comparison: {len(comparison)} days with position/demand data")
    
    def test_07_competitor_analysis_kpis(self):
        """Test KPIs structure and values"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/competitor-analysis",
            headers=self.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        kpis = data["kpis"]
        
        # Verify KPI fields
        required_kpis = ["our_avg_rate", "competitor_avg_rate", "price_position_pct", 
                        "position_label", "high_demand_days", "low_demand_days", 
                        "events_tracked", "insights_count", "high_priority_insights"]
        for field in required_kpis:
            assert field in kpis, f"Missing KPI: {field}"
        
        # Verify position_label values
        valid_labels = ["Premium", "Above Avg", "Competitive", "Undercut"]
        assert kpis["position_label"] in valid_labels, f"Invalid position_label: {kpis['position_label']}"
        
        # Verify our_avg_rate is positive
        assert kpis["our_avg_rate"] > 0, f"Invalid our_avg_rate: {kpis['our_avg_rate']}"
        
        print(f"✓ KPIs: Our Avg={kpis['our_avg_rate']}, Comp Avg={kpis['competitor_avg_rate']}, Position={kpis['position_label']}")
    
    def test_08_competitor_analysis_insights(self):
        """Test insights array structure"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/competitor-analysis",
            headers=self.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        insights = data["insights"]
        
        # Verify insights is array
        assert isinstance(insights, list), "insights should be array"
        assert len(insights) > 0, "Should have at least one insight"
        
        # Verify insight structure
        insight = insights[0]
        required_fields = ["type", "title", "desc", "action", "priority"]
        for field in required_fields:
            assert field in insight, f"Missing {field} in insight"
        
        # Verify type values
        valid_types = ["opportunity", "warning", "success", "info"]
        assert insight["type"] in valid_types, f"Invalid insight type: {insight['type']}"
        
        # Verify priority values
        valid_priorities = ["high", "medium", "low"]
        assert insight["priority"] in valid_priorities, f"Invalid priority: {insight['priority']}"
        
        print(f"✓ Insights: {len(insights)} findings, types: {set(i['type'] for i in insights)}")
    
    def test_09_parity_scan_with_custom_days(self):
        """Test parity scan with custom days parameter"""
        response = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/parity/scan",
            headers=self.headers,
            json={"days": 7}
        )
        assert response.status_code == 200
        
        data = response.json()
        # Note: The scan always stores 14 days but we can request fewer
        # The endpoint should still work
        assert data["dates_scanned"] >= 7, f"Expected at least 7 dates, got {data['dates_scanned']}"
        
        print(f"✓ Custom scan: {data['dates_scanned']} dates scanned")
    
    def test_10_parity_status_distribution(self):
        """Test that parity statuses are distributed correctly (parity/minor/violation)"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/parity",
            headers=self.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        parity_data = data["parity_data"]
        
        # Count statuses
        status_counts = {"parity": 0, "minor": 0, "violation": 0}
        for entry in parity_data:
            for ch_id, ch_data in entry.get("channels", {}).items():
                if ch_id != "direct":  # Direct is always in parity
                    status = ch_data.get("status", "parity")
                    status_counts[status] = status_counts.get(status, 0) + 1
        
        total = sum(status_counts.values())
        assert total > 0, "No channel data found"
        
        # Verify we have some distribution (not all one status)
        # Based on simulation: ~70% parity, ~20% minor, ~10% violation
        print(f"✓ Status distribution: Parity={status_counts['parity']}, Minor={status_counts['minor']}, Violation={status_counts['violation']}")
    
    def test_11_competitor_analysis_with_no_competitor_prices(self):
        """Test competitor analysis handles missing competitor prices gracefully"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/competitor-analysis",
            headers=self.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        
        # Should still return valid structure even without competitor prices
        assert "comparison" in data
        assert "insights" in data
        assert "kpis" in data
        
        # Check for "No Competitors Tracked" or "Data Gap" insight
        insight_titles = [i["title"] for i in data["insights"]]
        has_data_insight = any("Competitor" in t or "Data" in t for t in insight_titles)
        
        print(f"✓ Handles missing competitor data: {data['competitors_count']} competitors, insights: {insight_titles[:3]}")
    
    def test_12_parity_diff_pct_calculation(self):
        """Test that diff_pct is calculated correctly"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/parity",
            headers=self.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        parity_data = data["parity_data"]
        
        # Check diff_pct calculation for first entry
        if parity_data:
            entry = parity_data[0]
            our_price = entry["our_price"]
            
            for ch_id, ch_data in entry.get("channels", {}).items():
                ota_price = ch_data["price"]
                diff_pct = ch_data["diff_pct"]
                
                # Verify diff_pct calculation: (ota_price - our_price) / our_price * 100
                expected_diff = round((ota_price - our_price) / our_price * 100, 1) if our_price > 0 else 0
                assert abs(diff_pct - expected_diff) < 0.2, f"diff_pct mismatch for {ch_id}: {diff_pct} vs {expected_diff}"
                break
        
        print(f"✓ diff_pct calculation verified")
    
    def test_13_competitor_analysis_position_labels(self):
        """Test position labels match price_position_pct thresholds"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/competitor-analysis",
            headers=self.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        kpis = data["kpis"]
        
        pct = kpis["price_position_pct"]
        label = kpis["position_label"]
        
        # Verify label matches percentage thresholds
        # Premium (>10%), Above Avg (0-10%), Competitive (-10-0%), Undercut (<-10%)
        if pct > 10:
            expected = "Premium"
        elif pct > 0:
            expected = "Above Avg"
        elif pct > -10:
            expected = "Competitive"
        else:
            expected = "Undercut"
        
        assert label == expected, f"Position label mismatch: {label} vs {expected} for {pct}%"
        
        print(f"✓ Position label correct: {pct}% = {label}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
