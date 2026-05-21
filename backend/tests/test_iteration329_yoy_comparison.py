"""
Test YoY Comparison Feature (Iteration 329)
Tests the Year-over-Year comparison strip in the Performance Report:
- Backend: annual_forecast.yoy_comparison object with prev_year_total_revenue, delta_pct, etc.
- Backend: monthly[] items with prev_year_revenue, prev_year_month_key, yoy_delta_pct
- Property with historical bookings (aldgate-flats) should have YoY data
- Property without historical bookings (whitechapel-grand) should have prev_year_total_revenue=0
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestYoYComparison:
    """YoY Comparison feature tests for Performance Report"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token for all tests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        self.token = response.json().get("token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_aldgate_flats_has_yoy_comparison(self):
        """Test aldgate-flats performance endpoint returns yoy_comparison with historical data"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/aldgate-flats/performance",
            headers=self.headers
        )
        assert response.status_code == 200, f"API failed: {response.text}"
        
        data = response.json()
        assert "annual_forecast" in data, "annual_forecast missing from response"
        
        af = data["annual_forecast"]
        assert "yoy_comparison" in af, "yoy_comparison missing from annual_forecast"
        
        yoy = af["yoy_comparison"]
        # Verify all required fields exist
        assert "prev_year_total_revenue" in yoy, "prev_year_total_revenue missing"
        assert "this_year_forecast_revenue" in yoy, "this_year_forecast_revenue missing"
        assert "delta_revenue" in yoy, "delta_revenue missing"
        assert "delta_pct" in yoy, "delta_pct missing"
        assert "months_with_history" in yoy, "months_with_history missing"
        assert "horizon_months" in yoy, "horizon_months missing"
        
        # aldgate-flats has historical bookings, so prev_year_total_revenue should be > 0
        assert yoy["prev_year_total_revenue"] > 0, f"Expected prev_year_total_revenue > 0, got {yoy['prev_year_total_revenue']}"
        assert yoy["months_with_history"] > 0, f"Expected months_with_history > 0, got {yoy['months_with_history']}"
        assert yoy["delta_pct"] is not None, "delta_pct should not be null when historical data exists"
        
        print(f"✓ aldgate-flats YoY: prev_year={yoy['prev_year_total_revenue']}, delta_pct={yoy['delta_pct']}%, months_with_history={yoy['months_with_history']}")
    
    def test_aldgate_flats_monthly_has_yoy_fields(self):
        """Test aldgate-flats monthly data includes prev_year_revenue, prev_year_month_key, yoy_delta_pct"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/aldgate-flats/performance",
            headers=self.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        monthly = data["annual_forecast"]["monthly"]
        assert len(monthly) > 0, "monthly array is empty"
        
        # Check first month has all required YoY fields
        first_month = monthly[0]
        assert "prev_year_revenue" in first_month, "prev_year_revenue missing from monthly item"
        assert "prev_year_month_key" in first_month, "prev_year_month_key missing from monthly item"
        assert "yoy_delta_pct" in first_month, "yoy_delta_pct missing from monthly item"
        
        # Verify prev_year_month_key format (YYYY-MM)
        assert len(first_month["prev_year_month_key"]) == 7, f"Invalid prev_year_month_key format: {first_month['prev_year_month_key']}"
        assert "-" in first_month["prev_year_month_key"], f"Invalid prev_year_month_key format: {first_month['prev_year_month_key']}"
        
        # Count months with historical data
        months_with_data = sum(1 for m in monthly if m["prev_year_revenue"] > 0)
        print(f"✓ aldgate-flats monthly: {months_with_data}/{len(monthly)} months have prev_year_revenue > 0")
    
    def test_whitechapel_grand_no_historical_data(self):
        """Test whitechapel-grand (no historical bookings) returns yoy_comparison with prev_year_total_revenue=0"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/whitechapel-grand/performance",
            headers=self.headers
        )
        assert response.status_code == 200, f"API failed: {response.text}"
        
        data = response.json()
        assert "annual_forecast" in data, "annual_forecast missing from response"
        
        af = data["annual_forecast"]
        assert "yoy_comparison" in af, "yoy_comparison missing from annual_forecast"
        
        yoy = af["yoy_comparison"]
        # whitechapel-grand has no historical bookings
        assert yoy["prev_year_total_revenue"] == 0, f"Expected prev_year_total_revenue=0, got {yoy['prev_year_total_revenue']}"
        assert yoy["delta_pct"] is None, f"Expected delta_pct=null when no historical data, got {yoy['delta_pct']}"
        assert yoy["months_with_history"] == 0, f"Expected months_with_history=0, got {yoy['months_with_history']}"
        
        print(f"✓ whitechapel-grand YoY: prev_year={yoy['prev_year_total_revenue']}, delta_pct={yoy['delta_pct']}, months_with_history={yoy['months_with_history']}")
    
    def test_yoy_delta_calculation(self):
        """Test YoY delta calculation is correct"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/aldgate-flats/performance",
            headers=self.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        yoy = data["annual_forecast"]["yoy_comparison"]
        
        # Verify delta_revenue calculation
        expected_delta = round(yoy["this_year_forecast_revenue"] - yoy["prev_year_total_revenue"], 2)
        assert abs(yoy["delta_revenue"] - expected_delta) < 0.1, f"delta_revenue mismatch: expected {expected_delta}, got {yoy['delta_revenue']}"
        
        # Verify delta_pct calculation (if prev_year > 0)
        if yoy["prev_year_total_revenue"] > 0:
            expected_pct = round(((yoy["this_year_forecast_revenue"] - yoy["prev_year_total_revenue"]) / yoy["prev_year_total_revenue"]) * 100, 1)
            assert abs(yoy["delta_pct"] - expected_pct) < 0.2, f"delta_pct mismatch: expected {expected_pct}, got {yoy['delta_pct']}"
        
        print(f"✓ YoY delta calculation verified: delta_revenue={yoy['delta_revenue']}, delta_pct={yoy['delta_pct']}%")
    
    def test_regression_annual_forecast_fields(self):
        """Regression test: existing annual_forecast fields still present"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/aldgate-flats/performance",
            headers=self.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        af = data["annual_forecast"]
        
        # Check existing fields are still present
        assert "annual_revenue" in af, "annual_revenue missing"
        assert "revpar" in af, "revpar missing"
        assert "total_rooms" in af, "total_rooms missing"
        assert "adr" in af, "adr missing"
        assert "avg_occupancy_pct" in af, "avg_occupancy_pct missing"
        assert "monthly" in af, "monthly missing"
        assert "methodology" in af, "methodology missing"
        
        # Check monthly items have existing fields
        if af["monthly"]:
            m = af["monthly"][0]
            assert "year" in m, "year missing from monthly"
            assert "month" in m, "month missing from monthly"
            assert "revenue" in m, "revenue missing from monthly"
            assert "adr" in m, "adr missing from monthly"
            assert "occupancy_pct" in m, "occupancy_pct missing from monthly"
        
        print(f"✓ Regression: all existing annual_forecast fields present")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
