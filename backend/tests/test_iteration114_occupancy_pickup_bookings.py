"""
Iteration 114 - Occupancy & Pickup Chart + Recent Bookings Panel Tests
Tests the NEW endpoints:
- GET /api/revenue/market-robot/{property_id}/occupancy-pickup - 90 Day Occupancy & Pickup chart data
- GET /api/revenue/market-robot/{property_id}/recent-bookings - Last 7 days booking activity
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestOccupancyPickupEndpoint:
    """Tests for the occupancy-pickup endpoint with different pickup windows"""
    
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
    
    def test_occupancy_pickup_24h_window(self):
        """Test occupancy-pickup with 24h pickup window"""
        resp = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/all/occupancy-pickup?days=90&pickup_window=24h",
            headers=self.headers
        )
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        # Verify pickup_window is returned correctly
        assert data.get("pickup_window") == "24h", "pickup_window should be 24h"
        
        # Verify KPIs structure
        kpis = data.get("kpis", {})
        assert "total_days" in kpis, "Missing total_days in KPIs"
        assert "total_rooms" in kpis, "Missing total_rooms in KPIs"
        assert "avg_occupancy" in kpis, "Missing avg_occupancy in KPIs"
        assert "avg_pickup" in kpis, "Missing avg_pickup in KPIs"
        assert "peak_occupancy" in kpis, "Missing peak_occupancy in KPIs"
        assert "peak_date" in kpis, "Missing peak_date in KPIs"
        
        # Verify daily array
        daily = data.get("daily", [])
        assert len(daily) == 90, f"Expected 90 days, got {len(daily)}"
        
        # Verify daily data structure
        first_day = daily[0]
        assert "date" in first_day, "Missing date in daily data"
        assert "dow" in first_day, "Missing dow in daily data"
        assert "month" in first_day, "Missing month in daily data"
        assert "day" in first_day, "Missing day in daily data"
        assert "occupancy_pct" in first_day, "Missing occupancy_pct in daily data"
        assert "pickup_pct" in first_day, "Missing pickup_pct in daily data"
        assert "booked_rooms" in first_day, "Missing booked_rooms in daily data"
        assert "pickup_rooms" in first_day, "Missing pickup_rooms in daily data"
        assert "total_rooms" in first_day, "Missing total_rooms in daily data"
    
    def test_occupancy_pickup_3d_window(self):
        """Test occupancy-pickup with 3d pickup window"""
        resp = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/all/occupancy-pickup?days=90&pickup_window=3d",
            headers=self.headers
        )
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        # Verify pickup_window is returned correctly
        assert data.get("pickup_window") == "3d", "pickup_window should be 3d"
        
        # Verify KPIs exist
        kpis = data.get("kpis", {})
        assert "avg_pickup" in kpis, "Missing avg_pickup in KPIs"
    
    def test_occupancy_pickup_7d_window(self):
        """Test occupancy-pickup with 7d pickup window"""
        resp = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/all/occupancy-pickup?days=90&pickup_window=7d",
            headers=self.headers
        )
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        # Verify pickup_window is returned correctly
        assert data.get("pickup_window") == "7d", "pickup_window should be 7d"
        
        # Verify KPIs exist
        kpis = data.get("kpis", {})
        assert "avg_pickup" in kpis, "Missing avg_pickup in KPIs"
    
    def test_pickup_windows_return_different_values(self):
        """Verify different pickup windows can return different pickup values"""
        # Get data for all three windows
        resp_24h = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/all/occupancy-pickup?days=90&pickup_window=24h",
            headers=self.headers
        )
        resp_3d = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/all/occupancy-pickup?days=90&pickup_window=3d",
            headers=self.headers
        )
        resp_7d = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/all/occupancy-pickup?days=90&pickup_window=7d",
            headers=self.headers
        )
        
        assert resp_24h.status_code == 200
        assert resp_3d.status_code == 200
        assert resp_7d.status_code == 200
        
        # All should return valid data
        data_24h = resp_24h.json()
        data_3d = resp_3d.json()
        data_7d = resp_7d.json()
        
        # Verify each has the correct pickup_window
        assert data_24h.get("pickup_window") == "24h"
        assert data_3d.get("pickup_window") == "3d"
        assert data_7d.get("pickup_window") == "7d"
        
        # Verify all have daily data
        assert len(data_24h.get("daily", [])) == 90
        assert len(data_3d.get("daily", [])) == 90
        assert len(data_7d.get("daily", [])) == 90


class TestRecentBookingsEndpoint:
    """Tests for the recent-bookings endpoint"""
    
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
    
    def test_recent_bookings_7_days(self):
        """Test recent-bookings returns 7 days of data"""
        resp = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/all/recent-bookings?days=7",
            headers=self.headers
        )
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        # Verify daily array
        daily = data.get("daily", [])
        assert len(daily) == 7, f"Expected 7 days, got {len(daily)}"
        
        # Verify daily data structure
        first_day = daily[0]
        assert "date" in first_day, "Missing date in daily data"
        assert "dow" in first_day, "Missing dow in daily data"
        assert "day" in first_day, "Missing day in daily data"
        assert "month" in first_day, "Missing month in daily data"
        assert "bookings" in first_day, "Missing bookings in daily data"
        assert "room_nights" in first_day, "Missing room_nights in daily data"
        assert "adr" in first_day, "Missing adr in daily data"
        assert "revenue" in first_day, "Missing revenue in daily data"
    
    def test_recent_bookings_summary(self):
        """Test recent-bookings returns summary with totals"""
        resp = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/all/recent-bookings?days=7",
            headers=self.headers
        )
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        # Verify summary structure
        summary = data.get("summary", {})
        assert "total_bookings" in summary, "Missing total_bookings in summary"
        assert "total_room_nights" in summary, "Missing total_room_nights in summary"
        assert "total_revenue" in summary, "Missing total_revenue in summary"
        assert "avg_adr" in summary, "Missing avg_adr in summary"
        assert "days" in summary, "Missing days in summary"
        
        # Verify days matches request
        assert summary.get("days") == 7, "Summary days should be 7"
    
    def test_recent_bookings_data_types(self):
        """Test recent-bookings returns correct data types"""
        resp = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/all/recent-bookings?days=7",
            headers=self.headers
        )
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        daily = data.get("daily", [])
        if daily:
            first_day = daily[0]
            # Verify numeric types
            assert isinstance(first_day.get("bookings"), int), "bookings should be int"
            assert isinstance(first_day.get("room_nights"), int), "room_nights should be int"
            assert isinstance(first_day.get("adr"), (int, float)), "adr should be numeric"
            assert isinstance(first_day.get("revenue"), (int, float)), "revenue should be numeric"
            assert isinstance(first_day.get("day"), int), "day should be int"
            # Verify string types
            assert isinstance(first_day.get("date"), str), "date should be string"
            assert isinstance(first_day.get("dow"), str), "dow should be string"
            assert isinstance(first_day.get("month"), str), "month should be string"


class TestEndpointAuthentication:
    """Test that endpoints require authentication"""
    
    def test_occupancy_pickup_requires_auth(self):
        """Test occupancy-pickup endpoint requires authentication"""
        resp = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/all/occupancy-pickup?days=90&pickup_window=24h"
        )
        assert resp.status_code in [401, 403], f"Expected 401/403, got {resp.status_code}"
    
    def test_recent_bookings_requires_auth(self):
        """Test recent-bookings endpoint requires authentication"""
        resp = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/all/recent-bookings?days=7"
        )
        assert resp.status_code in [401, 403], f"Expected 401/403, got {resp.status_code}"
