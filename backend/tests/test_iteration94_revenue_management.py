"""
Iteration 94 - Revenue Management Module Backend Tests
Tests: Dashboard KPIs, Occupancy Heatmap, YOY Tables, Rate Calendar, Pricing Strategy
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://review-hub-108.preview.emergentagent.com')

class TestRevenueManagement:
    """Revenue Management API Tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        self.token = response.json().get("token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    # ==================== DASHBOARD KPIs ====================
    
    def test_dashboard_all_properties(self):
        """GET /api/revenue/dashboard/all - Returns KPIs for all properties"""
        response = requests.get(f"{BASE_URL}/api/revenue/dashboard/all", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert "last_month" in data
        assert "current_month" in data
        assert "next_month" in data
        assert "properties_count" in data
        
        # Verify KPI fields for each month
        for month_key in ["last_month", "current_month", "next_month"]:
            month_data = data[month_key]
            assert "revenue" in month_data
            assert "occupancy" in month_data
            assert "adr" in month_data
            assert "yoy" in month_data
            assert "label" in month_data
        
        print(f"Dashboard KPIs: Last={data['last_month']['revenue']}, Current={data['current_month']['revenue']}, Next={data['next_month']['revenue']}")
    
    def test_dashboard_specific_property(self):
        """GET /api/revenue/dashboard/{property_id} - Returns KPIs for specific property"""
        response = requests.get(f"{BASE_URL}/api/revenue/dashboard/aldgate-flats", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "last_month" in data
        assert "current_month" in data
        assert "next_month" in data
        assert data["properties_count"] == 1
        
        print(f"Aldgate Flats KPIs: Current Month Revenue={data['current_month']['revenue']}")
    
    def test_dashboard_requires_auth(self):
        """Dashboard endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/revenue/dashboard/all")
        assert response.status_code == 401
    
    # ==================== OCCUPANCY HEATMAP ====================
    
    def test_heatmap_default(self):
        """GET /api/revenue/heatmap - Returns occupancy data for all properties"""
        response = requests.get(f"{BASE_URL}/api/revenue/heatmap", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "dates" in data
        assert "properties" in data
        assert len(data["dates"]) == 30  # Default 30 days
        assert len(data["properties"]) > 0
        
        # Verify property structure
        prop = data["properties"][0]
        assert "property_id" in prop
        assert "name" in prop
        assert "total_rooms" in prop
        assert "daily" in prop
        
        # Verify daily data structure
        daily = prop["daily"][0]
        assert "date" in daily
        assert "occupancy" in daily
        assert "adr" in daily
        assert "booked" in daily
        assert "available" in daily
        
        print(f"Heatmap: {len(data['properties'])} properties, {len(data['dates'])} days")
    
    def test_heatmap_custom_days(self):
        """GET /api/revenue/heatmap?days=14 - Returns custom day range"""
        response = requests.get(f"{BASE_URL}/api/revenue/heatmap?days=14", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["dates"]) == 14
        print(f"Heatmap with 14 days: {data['dates'][0]} to {data['dates'][-1]}")
    
    def test_heatmap_requires_auth(self):
        """Heatmap endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/revenue/heatmap")
        assert response.status_code == 401
    
    # ==================== YOY TABLES ====================
    
    def test_yoy_tables(self):
        """GET /api/revenue/yoy-tables - Returns YOY revenue comparison per property"""
        response = requests.get(f"{BASE_URL}/api/revenue/yoy-tables", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) > 0
        
        # Verify property structure
        prop = data[0]
        assert "property_id" in prop
        assert "name" in prop
        assert "total_rooms" in prop
        assert "months" in prop
        
        # Verify month structure
        month = prop["months"][0]
        assert "month" in month
        assert "prev_rev" in month
        assert "curr_occ" in month
        assert "curr_adr" in month
        assert "curr_rev" in month
        assert "variance" in month
        assert "is_current" in month
        
        print(f"YOY Tables: {len(data)} properties, {len(prop['months'])} months each")
    
    def test_yoy_tables_requires_auth(self):
        """YOY Tables endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/revenue/yoy-tables")
        assert response.status_code == 401
    
    # ==================== RATE CALENDAR ====================
    
    def test_rate_calendar_default(self):
        """GET /api/revenue/rate-calendar/{property_id} - Returns rate calendar for current month"""
        response = requests.get(f"{BASE_URL}/api/revenue/rate-calendar/aldgate-flats", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "year" in data
        assert "month" in data
        assert "month_name" in data
        assert "room_type" in data
        assert "room_types" in data
        assert "total_rooms" in data
        assert "performance" in data
        assert "days" in data
        
        # Verify performance structure
        perf = data["performance"]
        assert "occupancy" in perf
        assert "expected_by_today" in perf
        assert "target" in perf
        
        # Verify day structure
        day = data["days"][0]
        assert "date" in day
        assert "day" in day
        assert "dow" in day
        assert "occupancy" in day
        assert "booked" in day
        assert "available" in day
        assert "is_full" in day
        assert "is_today" in day
        assert "base_rate" in day
        assert "recommended_rate" in day
        assert "pms_rate" in day
        
        print(f"Rate Calendar: {data['month_name']} {data['year']}, {len(data['days'])} days, {len(data['room_types'])} room types")
    
    def test_rate_calendar_custom_month(self):
        """GET /api/revenue/rate-calendar/{property_id}?year=2026&month=5 - Custom month"""
        response = requests.get(f"{BASE_URL}/api/revenue/rate-calendar/aldgate-flats?year=2026&month=5", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        
        assert data["year"] == 2026
        assert data["month"] == 5
        assert data["month_name"] == "May"
        assert len(data["days"]) == 31  # May has 31 days
        
        print(f"Rate Calendar May 2026: {len(data['days'])} days")
    
    def test_rate_calendar_room_type_filter(self):
        """GET /api/revenue/rate-calendar/{property_id}?room_type=... - Filter by room type"""
        # First get available room types
        response = requests.get(f"{BASE_URL}/api/revenue/rate-calendar/aldgate-flats", headers=self.headers)
        data = response.json()
        
        if len(data["room_types"]) > 1:
            room_type_id = data["room_types"][1]["id"]
            response2 = requests.get(f"{BASE_URL}/api/revenue/rate-calendar/aldgate-flats?room_type={room_type_id}", headers=self.headers)
            assert response2.status_code == 200
            data2 = response2.json()
            assert data2["room_type"]["id"] == room_type_id
            print(f"Rate Calendar filtered by room type: {data2['room_type']['name']}")
    
    def test_rate_calendar_today_highlighted(self):
        """Rate calendar marks today with is_today=true"""
        response = requests.get(f"{BASE_URL}/api/revenue/rate-calendar/aldgate-flats", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        
        # Find today's entry
        today_entries = [d for d in data["days"] if d["is_today"]]
        assert len(today_entries) == 1, "Exactly one day should be marked as today"
        print(f"Today highlighted: Day {today_entries[0]['day']}")
    
    def test_rate_calendar_dynamic_pricing(self):
        """Rate calendar applies dynamic pricing based on occupancy"""
        response = requests.get(f"{BASE_URL}/api/revenue/rate-calendar/aldgate-flats", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        
        # Check that recommended rates vary based on occupancy
        for day in data["days"]:
            base = day["base_rate"]
            recommended = day["recommended_rate"]
            occ = day["occupancy"]
            
            # Verify pricing logic: occ>=90 → +40%, >=75 → +20%, >=50 → base, >=25 → -15%, <25 → -30%
            if occ >= 90:
                expected = round(base * 1.4, 2)
            elif occ >= 75:
                expected = round(base * 1.2, 2)
            elif occ >= 50:
                expected = round(base * 1.0, 2)
            elif occ >= 25:
                expected = round(base * 0.85, 2)
            else:
                expected = round(base * 0.7, 2)
            
            assert recommended == expected, f"Day {day['day']}: Expected {expected}, got {recommended} for occ={occ}"
        
        print("Dynamic pricing verified for all days")
    
    def test_rate_calendar_requires_auth(self):
        """Rate calendar endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/revenue/rate-calendar/aldgate-flats")
        assert response.status_code == 401
    
    # ==================== PRICING STRATEGY ====================
    
    def test_pricing_strategy_get(self):
        """GET /api/revenue/pricing-strategy/{property_id} - Returns rooms setup and pricing rules"""
        response = requests.get(f"{BASE_URL}/api/revenue/pricing-strategy/aldgate-flats", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "rooms_setup" in data
        assert "strategy" in data
        
        # Verify rooms_setup structure
        assert len(data["rooms_setup"]) > 0
        room = data["rooms_setup"][0]
        assert "id" in room
        assert "name" in room
        assert "number_of_rooms" in room
        assert "reference_derived" in room
        assert "base_price" in room
        assert "min_price" in room
        assert "max_price" in room
        
        # First room should be Reference
        assert data["rooms_setup"][0]["reference_derived"] == "Reference"
        
        # Other rooms should be Derived
        for room in data["rooms_setup"][1:]:
            assert room["reference_derived"] == "Derived"
        
        # Verify strategy structure
        strategy = data["strategy"]
        assert "dow_adjustments" in strategy
        assert "monthly_adjustments" in strategy
        assert "occupancy_rules" in strategy
        
        print(f"Pricing Strategy: {len(data['rooms_setup'])} room types")
    
    def test_pricing_strategy_update(self):
        """PUT /api/revenue/pricing-strategy/{property_id} - Updates pricing strategy"""
        # Get current strategy
        response = requests.get(f"{BASE_URL}/api/revenue/pricing-strategy/aldgate-flats", headers=self.headers)
        current = response.json()
        
        # Update with new values
        new_strategy = {
            "dow_adjustments": {"fri": 10, "sat": 15, "sun": 5},
            "monthly_adjustments": {"jul": 20, "aug": 25, "dec": 30},
            "occupancy_rules": [{"min": 90, "max": 100, "adjustment": 40}]
        }
        
        response = requests.put(
            f"{BASE_URL}/api/revenue/pricing-strategy/aldgate-flats",
            headers=self.headers,
            json=new_strategy
        )
        assert response.status_code == 200
        
        # Verify update persisted
        response = requests.get(f"{BASE_URL}/api/revenue/pricing-strategy/aldgate-flats", headers=self.headers)
        data = response.json()
        
        assert data["strategy"]["dow_adjustments"]["fri"] == 10
        assert data["strategy"]["monthly_adjustments"]["jul"] == 20
        
        print("Pricing strategy updated and verified")
    
    def test_pricing_strategy_requires_auth(self):
        """Pricing strategy endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/revenue/pricing-strategy/aldgate-flats")
        assert response.status_code == 401


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
