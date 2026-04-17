"""
Iteration 117 - Revenue Intelligence Features Testing
Tests for 4 new revenue intelligence features:
1. Booking Pace & Pickup Velocity
2. Revenue Forecast Engine
3. Rate Recommendation Actions
4. What-If Simulator
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestRevenueIntelligence:
    """Revenue Intelligence API Tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        data = login_response.json()
        token = data.get("token")
        assert token, "No token in login response"
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        print(f"✓ Login successful, token obtained")
    
    # ==================== 1. BOOKING PACE & PICKUP VELOCITY ====================
    
    def test_booking_pace_endpoint_exists(self):
        """Test GET /api/revenue/intelligence/all/booking-pace returns 200"""
        response = self.session.get(f"{BASE_URL}/api/revenue/intelligence/all/booking-pace?days=7")
        assert response.status_code == 200, f"Booking pace endpoint failed: {response.status_code} - {response.text}"
        print(f"✓ Booking pace endpoint returns 200")
    
    def test_booking_pace_response_structure(self):
        """Test booking pace response has required fields: daily_pace, kpis, alerts"""
        response = self.session.get(f"{BASE_URL}/api/revenue/intelligence/all/booking-pace?days=7")
        assert response.status_code == 200
        data = response.json()
        
        # Check top-level fields
        assert "daily_pace" in data, "Missing daily_pace field"
        assert "kpis" in data, "Missing kpis field"
        assert "alerts" in data, "Missing alerts field"
        
        # Check KPIs structure
        kpis = data["kpis"]
        required_kpi_fields = ["total_this_year", "total_last_year", "diff", "pace_status", "pickup_24h", "velocity_change_pct"]
        for field in required_kpi_fields:
            assert field in kpis, f"Missing KPI field: {field}"
        
        print(f"✓ Booking pace response structure valid")
        print(f"  - This Year: {kpis['total_this_year']}, Last Year: {kpis['total_last_year']}")
        print(f"  - Diff: {kpis['diff']}, Pace Status: {kpis['pace_status']}")
        print(f"  - 24h Pickup: {kpis['pickup_24h']}, Velocity Change: {kpis['velocity_change_pct']}%")
    
    def test_booking_pace_daily_data(self):
        """Test daily_pace array has proper structure"""
        response = self.session.get(f"{BASE_URL}/api/revenue/intelligence/all/booking-pace?days=7")
        assert response.status_code == 200
        data = response.json()
        
        daily_pace = data["daily_pace"]
        assert len(daily_pace) == 7, f"Expected 7 days, got {len(daily_pace)}"
        
        # Check first day structure
        day = daily_pace[0]
        assert "date" in day
        assert "dow" in day
        assert "this_year" in day
        assert "last_year" in day
        assert "diff_bookings" in day
        assert "pace" in day
        
        # Check this_year structure
        ty = day["this_year"]
        assert "bookings" in ty
        assert "revenue" in ty
        assert "room_nights" in ty
        
        print(f"✓ Daily pace data structure valid for 7 days")
    
    def test_booking_pace_alerts(self):
        """Test alerts array exists and has proper structure"""
        response = self.session.get(f"{BASE_URL}/api/revenue/intelligence/all/booking-pace?days=30")
        assert response.status_code == 200
        data = response.json()
        
        alerts = data["alerts"]
        assert isinstance(alerts, list), "Alerts should be a list"
        assert len(alerts) > 0, "Should have at least one alert"
        
        alert = alerts[0]
        assert "type" in alert, "Alert missing type"
        assert "message" in alert, "Alert missing message"
        assert alert["type"] in ["positive", "warning", "info"], f"Invalid alert type: {alert['type']}"
        
        print(f"✓ Alerts structure valid, {len(alerts)} alerts found")
        for a in alerts:
            print(f"  - [{a['type']}] {a['message'][:60]}...")
    
    def test_booking_pace_day_ranges(self):
        """Test different day ranges: 7, 14, 30, 60, 90"""
        for days in [7, 14, 30, 60, 90]:
            response = self.session.get(f"{BASE_URL}/api/revenue/intelligence/all/booking-pace?days={days}")
            assert response.status_code == 200, f"Failed for {days} days"
            data = response.json()
            assert len(data["daily_pace"]) == days, f"Expected {days} days, got {len(data['daily_pace'])}"
        print(f"✓ All day ranges (7, 14, 30, 60, 90) work correctly")
    
    # ==================== 2. REVENUE FORECAST ENGINE ====================
    
    def test_forecast_endpoint_exists(self):
        """Test GET /api/revenue/intelligence/all/forecast returns 200"""
        response = self.session.get(f"{BASE_URL}/api/revenue/intelligence/all/forecast?days=30")
        assert response.status_code == 200, f"Forecast endpoint failed: {response.status_code} - {response.text}"
        print(f"✓ Revenue forecast endpoint returns 200")
    
    def test_forecast_response_structure(self):
        """Test forecast response has required fields"""
        response = self.session.get(f"{BASE_URL}/api/revenue/intelligence/all/forecast?days=30")
        assert response.status_code == 200
        data = response.json()
        
        # Check top-level fields
        assert "forecast_daily" in data, "Missing forecast_daily"
        assert "monthly_forecast" in data, "Missing monthly_forecast"
        assert "kpis" in data, "Missing kpis"
        
        # Check KPIs
        kpis = data["kpis"]
        required_kpi_fields = ["projected_revenue", "projected_avg_adr", "projected_avg_occ", "projected_revpar", "yoy_change_pct"]
        for field in required_kpi_fields:
            assert field in kpis, f"Missing KPI field: {field}"
        
        print(f"✓ Forecast response structure valid")
        print(f"  - Projected Revenue: £{kpis['projected_revenue']:,.2f}")
        print(f"  - Projected ADR: £{kpis['projected_avg_adr']:.2f}")
        print(f"  - Projected Occupancy: {kpis['projected_avg_occ']}%")
        print(f"  - Projected RevPAR: £{kpis['projected_revpar']:.2f}")
        print(f"  - YoY Change: +{kpis['yoy_change_pct']}%")
    
    def test_forecast_daily_data(self):
        """Test forecast_daily array structure"""
        response = self.session.get(f"{BASE_URL}/api/revenue/intelligence/all/forecast?days=30")
        assert response.status_code == 200
        data = response.json()
        
        forecast_daily = data["forecast_daily"]
        assert len(forecast_daily) == 30, f"Expected 30 days, got {len(forecast_daily)}"
        
        day = forecast_daily[0]
        required_fields = ["date", "dow", "projected_occupancy", "projected_adr", "projected_revpar", "projected_revenue"]
        for field in required_fields:
            assert field in day, f"Missing field: {field}"
        
        print(f"✓ Forecast daily data structure valid for 30 days")
    
    def test_forecast_monthly_breakdown(self):
        """Test monthly_forecast array structure"""
        response = self.session.get(f"{BASE_URL}/api/revenue/intelligence/all/forecast?days=90")
        assert response.status_code == 200
        data = response.json()
        
        monthly = data["monthly_forecast"]
        assert len(monthly) > 0, "Should have at least one month"
        
        month = monthly[0]
        assert "month" in month
        assert "label" in month
        assert "projected_revenue" in month
        assert "avg_occupancy" in month
        
        print(f"✓ Monthly forecast structure valid, {len(monthly)} months")
        for m in monthly:
            print(f"  - {m['label']}: £{m['projected_revenue']:,.2f} ({m['avg_occupancy']}% occ)")
    
    def test_forecast_day_ranges(self):
        """Test different forecast day ranges: 30, 60, 90, 180, 365"""
        for days in [30, 60, 90, 180, 365]:
            response = self.session.get(f"{BASE_URL}/api/revenue/intelligence/all/forecast?days={days}")
            assert response.status_code == 200, f"Failed for {days} days"
            data = response.json()
            assert len(data["forecast_daily"]) == days, f"Expected {days} days, got {len(data['forecast_daily'])}"
        print(f"✓ All forecast day ranges (30, 60, 90, 180, 365) work correctly")
    
    # ==================== 3. RATE RECOMMENDATION ACTIONS ====================
    
    def test_recommendations_endpoint_exists(self):
        """Test GET /api/revenue/intelligence/all/recommendations returns 200"""
        response = self.session.get(f"{BASE_URL}/api/revenue/intelligence/all/recommendations")
        assert response.status_code == 200, f"Recommendations endpoint failed: {response.status_code} - {response.text}"
        print(f"✓ Rate recommendations endpoint returns 200")
    
    def test_recommendations_response_structure(self):
        """Test recommendations response has required fields"""
        response = self.session.get(f"{BASE_URL}/api/revenue/intelligence/all/recommendations")
        assert response.status_code == 200
        data = response.json()
        
        assert "recommendations" in data, "Missing recommendations"
        assert "kpis" in data, "Missing kpis"
        
        # Check KPIs
        kpis = data["kpis"]
        required_kpi_fields = ["total_actions", "increases", "decreases", "critical"]
        for field in required_kpi_fields:
            assert field in kpis, f"Missing KPI field: {field}"
        
        print(f"✓ Recommendations response structure valid")
        print(f"  - Total Actions: {kpis['total_actions']}")
        print(f"  - Increases: {kpis['increases']}, Decreases: {kpis['decreases']}")
        print(f"  - Critical: {kpis['critical']}")
    
    def test_recommendations_card_structure(self):
        """Test individual recommendation card structure"""
        response = self.session.get(f"{BASE_URL}/api/revenue/intelligence/all/recommendations")
        assert response.status_code == 200
        data = response.json()
        
        recs = data["recommendations"]
        if len(recs) > 0:
            rec = recs[0]
            required_fields = ["id", "date", "dow", "current_rate", "recommended_rate", "diff", "diff_pct", "action", "reasons", "priority"]
            for field in required_fields:
                assert field in rec, f"Missing field: {field}"
            
            assert rec["action"] in ["increase", "decrease"], f"Invalid action: {rec['action']}"
            assert rec["priority"] in ["critical", "high", "medium", "low"], f"Invalid priority: {rec['priority']}"
            
            print(f"✓ Recommendation card structure valid")
            print(f"  - Date: {rec['date']} ({rec['dow']})")
            print(f"  - Current: £{rec['current_rate']} → Recommended: £{rec['recommended_rate']}")
            print(f"  - Action: {rec['action']}, Priority: {rec['priority']}")
            print(f"  - Reasons: {', '.join(rec['reasons'][:2])}")
        else:
            print(f"✓ No recommendations needed (all rates optimized)")
    
    def test_accept_recommendation(self):
        """Test POST /api/revenue/intelligence/all/recommendations/accept"""
        # First get recommendations
        response = self.session.get(f"{BASE_URL}/api/revenue/intelligence/all/recommendations")
        assert response.status_code == 200
        data = response.json()
        
        recs = data["recommendations"]
        if len(recs) > 0:
            rec = recs[0]
            # Accept the recommendation
            accept_response = self.session.post(
                f"{BASE_URL}/api/revenue/intelligence/all/recommendations/accept",
                json={"date": rec["date"], "rate": rec["recommended_rate"]}
            )
            assert accept_response.status_code == 200, f"Accept failed: {accept_response.text}"
            result = accept_response.json()
            assert "applied" in result and result["applied"] == True
            print(f"✓ Accept recommendation works - Rate for {rec['date']} set to £{rec['recommended_rate']}")
        else:
            # Test with a dummy date
            future_date = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")
            accept_response = self.session.post(
                f"{BASE_URL}/api/revenue/intelligence/all/recommendations/accept",
                json={"date": future_date, "rate": 150.00}
            )
            assert accept_response.status_code == 200
            print(f"✓ Accept recommendation endpoint works (tested with dummy data)")
    
    def test_accept_all_recommendations(self):
        """Test POST /api/revenue/intelligence/all/recommendations/accept-all"""
        # Get recommendations
        response = self.session.get(f"{BASE_URL}/api/revenue/intelligence/all/recommendations")
        assert response.status_code == 200
        data = response.json()
        
        recs = data["recommendations"][:3]  # Only accept first 3 to avoid too many changes
        
        accept_all_response = self.session.post(
            f"{BASE_URL}/api/revenue/intelligence/all/recommendations/accept-all",
            json={"recommendations": recs}
        )
        assert accept_all_response.status_code == 200, f"Accept-all failed: {accept_all_response.text}"
        result = accept_all_response.json()
        assert "applied" in result
        print(f"✓ Accept-all endpoint works - Applied {result['applied']} recommendations")
    
    # ==================== 4. WHAT-IF SIMULATOR ====================
    
    def test_whatif_endpoint_exists(self):
        """Test POST /api/revenue/intelligence/all/what-if returns 200"""
        today = datetime.now().strftime("%Y-%m-%d")
        future = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        
        response = self.session.post(f"{BASE_URL}/api/revenue/intelligence/all/what-if", json={
            "rate_change_pct": 10,
            "date_from": today,
            "date_to": future
        })
        assert response.status_code == 200, f"What-if endpoint failed: {response.status_code} - {response.text}"
        print(f"✓ What-if simulator endpoint returns 200")
    
    def test_whatif_response_structure(self):
        """Test what-if response has required fields"""
        today = datetime.now().strftime("%Y-%m-%d")
        future = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        
        response = self.session.post(f"{BASE_URL}/api/revenue/intelligence/all/what-if", json={
            "rate_change_pct": 10,
            "date_from": today,
            "date_to": future
        })
        assert response.status_code == 200
        data = response.json()
        
        # Check top-level fields
        assert "simulation" in data, "Missing simulation"
        assert "current" in data, "Missing current"
        assert "projected" in data, "Missing projected"
        assert "impact" in data, "Missing impact"
        
        # Check current scenario
        current = data["current"]
        assert "total_revenue" in current
        assert "avg_occupancy" in current
        assert "avg_adr" in current
        assert "total_rooms_sold" in current
        
        # Check projected scenario
        projected = data["projected"]
        assert "total_revenue" in projected
        assert "avg_occupancy" in projected
        assert "avg_adr" in projected
        
        # Check impact
        impact = data["impact"]
        assert "revenue_diff" in impact
        assert "verdict" in impact
        assert "recommendation" in impact
        
        print(f"✓ What-if response structure valid")
        print(f"  - Current Revenue: £{current['total_revenue']:,.2f}")
        print(f"  - Projected Revenue: £{projected['total_revenue']:,.2f}")
        print(f"  - Revenue Diff: £{impact['revenue_diff']:,.2f}")
        print(f"  - Verdict: {impact['verdict']}")
    
    def test_whatif_positive_rate_change(self):
        """Test +10% rate change simulation"""
        today = datetime.now().strftime("%Y-%m-%d")
        future = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        
        response = self.session.post(f"{BASE_URL}/api/revenue/intelligence/all/what-if", json={
            "rate_change_pct": 10,
            "date_from": today,
            "date_to": future
        })
        assert response.status_code == 200
        data = response.json()
        
        # With +10% rate, ADR should increase
        assert data["projected"]["avg_adr"] > data["current"]["avg_adr"], "ADR should increase with +10% rate"
        
        print(f"✓ +10% rate change: ADR £{data['current']['avg_adr']:.2f} → £{data['projected']['avg_adr']:.2f}")
        print(f"  - Recommendation: {data['impact']['recommendation'][:80]}...")
    
    def test_whatif_negative_rate_change(self):
        """Test -10% rate change simulation"""
        today = datetime.now().strftime("%Y-%m-%d")
        future = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        
        response = self.session.post(f"{BASE_URL}/api/revenue/intelligence/all/what-if", json={
            "rate_change_pct": -10,
            "date_from": today,
            "date_to": future
        })
        assert response.status_code == 200
        data = response.json()
        
        # With -10% rate, ADR should decrease
        assert data["projected"]["avg_adr"] < data["current"]["avg_adr"], "ADR should decrease with -10% rate"
        
        print(f"✓ -10% rate change: ADR £{data['current']['avg_adr']:.2f} → £{data['projected']['avg_adr']:.2f}")
        print(f"  - Verdict: {data['impact']['verdict']}")
    
    def test_whatif_verdict_types(self):
        """Test different verdict types based on rate changes"""
        today = datetime.now().strftime("%Y-%m-%d")
        future = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        
        verdicts = []
        for pct in [10, -10, 0]:
            response = self.session.post(f"{BASE_URL}/api/revenue/intelligence/all/what-if", json={
                "rate_change_pct": pct,
                "date_from": today,
                "date_to": future
            })
            assert response.status_code == 200
            data = response.json()
            verdicts.append((pct, data["impact"]["verdict"]))
        
        print(f"✓ Verdict types tested:")
        for pct, verdict in verdicts:
            print(f"  - {pct:+d}% rate change → {verdict}")
    
    def test_whatif_daily_comparison(self):
        """Test daily_comparison array in what-if response"""
        today = datetime.now().strftime("%Y-%m-%d")
        future = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        
        response = self.session.post(f"{BASE_URL}/api/revenue/intelligence/all/what-if", json={
            "rate_change_pct": 15,
            "date_from": today,
            "date_to": future
        })
        assert response.status_code == 200
        data = response.json()
        
        assert "daily_comparison" in data, "Missing daily_comparison"
        daily = data["daily_comparison"]
        assert len(daily) == 8, f"Expected 8 days, got {len(daily)}"  # inclusive range
        
        day = daily[0]
        required_fields = ["date", "dow", "current_rate", "new_rate", "current_occ", "new_occ", "current_rev", "new_rev", "rev_diff"]
        for field in required_fields:
            assert field in day, f"Missing field: {field}"
        
        print(f"✓ Daily comparison structure valid for 8 days")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
