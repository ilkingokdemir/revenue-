"""
Iteration 124 - Testing Displacement Analysis, LOS Optimizer, and Mobile Companion APIs
Tests for:
1. POST /api/revenue/displacement/analyze - Group booking displacement analysis
2. POST /api/revenue/displacement/save - Save displacement decision
3. GET /api/revenue/los-optimizer/{property_id} - LOS analysis with recommendations
4. POST /api/revenue/los-optimizer/{property_id}/restriction - Create LOS restriction
5. GET /api/mobile/dashboard/{property_id} - Mobile dashboard KPIs
6. GET /api/mobile/arrivals/{property_id} - Today's arrivals
7. GET /api/mobile/housekeeping/{property_id} - Housekeeping status
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuth:
    """Authentication for all tests"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        """Get authenticated session"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        
        if login_response.status_code != 200:
            pytest.skip(f"Authentication failed: {login_response.status_code}")
        
        return session


class TestDisplacementAnalysis(TestAuth):
    """Displacement Analysis API tests"""
    
    def test_displacement_analyze_basic(self, auth_session):
        """Test basic displacement analysis"""
        response = auth_session.post(f"{BASE_URL}/api/revenue/displacement/analyze", json={
            "property_id": "aldgate-flats",
            "check_in": "2026-04-20",
            "check_out": "2026-04-23",
            "rooms_requested": 5,
            "group_rate": 70,
            "group_name": "TEST_Tech Conference"
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify recommendation structure
        assert "recommendation" in data
        assert data["recommendation"] in ["ACCEPT", "REJECT", "NEUTRAL"]
        assert "confidence" in data
        assert isinstance(data["confidence"], int)
        assert 0 <= data["confidence"] <= 100
        
        # Verify group data
        assert "group" in data
        assert data["group"]["rooms"] == 5
        assert data["group"]["rate"] == 70
        assert data["group"]["nights"] == 3
        assert data["group"]["total_revenue"] == 70 * 5 * 3  # 1050
        
        # Verify individual comparison
        assert "individual" in data
        assert "avg_rate" in data["individual"]
        assert "fill_probability" in data["individual"]
        assert "total_revenue" in data["individual"]
        
        # Verify displacement cost
        assert "displacement_cost" in data
        
        # Verify daily analysis
        assert "daily_analysis" in data
        assert len(data["daily_analysis"]) == 3  # 3 nights
        
        # Verify risks
        assert "risks" in data
        assert isinstance(data["risks"], list)
        
        print(f"Displacement Analysis: {data['recommendation']} (confidence: {data['confidence']}%)")
        print(f"Group Revenue: £{data['group']['total_revenue']}, Individual Est: £{data['individual']['total_revenue']}")
        print(f"Displacement Cost: £{data['displacement_cost']}")
    
    def test_displacement_analyze_missing_dates(self, auth_session):
        """Test displacement analysis with missing dates"""
        response = auth_session.post(f"{BASE_URL}/api/revenue/displacement/analyze", json={
            "property_id": "aldgate-flats",
            "rooms_requested": 5,
            "group_rate": 70
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert "check_in" in data["error"].lower() or "check_out" in data["error"].lower()
    
    def test_displacement_analyze_large_group(self, auth_session):
        """Test displacement analysis with large group (capacity warning)"""
        response = auth_session.post(f"{BASE_URL}/api/revenue/displacement/analyze", json={
            "property_id": "aldgate-flats",
            "check_in": "2026-05-01",
            "check_out": "2026-05-05",
            "rooms_requested": 10,  # Large group
            "group_rate": 60,
            "group_name": "TEST_Large Conference"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have capacity risk factor
        risk_types = [r["type"] for r in data.get("risks", [])]
        # May have capacity warning if 10 rooms > 30% of total
        print(f"Risk factors: {risk_types}")
    
    def test_displacement_save_decision(self, auth_session):
        """Test saving displacement decision"""
        response = auth_session.post(f"{BASE_URL}/api/revenue/displacement/save", json={
            "group_name": "TEST_Save Decision Group",
            "recommendation": "ACCEPT",
            "decision": "accepted",
            "group_revenue": 1500,
            "displacement_cost": -200,
            "notes": "Good deal for low season"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert "id" in data
        assert data["group_name"] == "TEST_Save Decision Group"
        assert data["decision"] == "accepted"
        assert data["group_revenue"] == 1500
        print(f"Saved displacement decision: {data['id']}")
    
    def test_displacement_history(self, auth_session):
        """Test getting displacement history"""
        response = auth_session.get(f"{BASE_URL}/api/revenue/displacement/history")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "analyses" in data
        assert isinstance(data["analyses"], list)
        print(f"Displacement history: {len(data['analyses'])} records")


class TestLOSOptimizer(TestAuth):
    """Length of Stay Optimizer API tests"""
    
    def test_los_optimizer_analysis(self, auth_session):
        """Test LOS optimizer analysis"""
        response = auth_session.get(f"{BASE_URL}/api/revenue/los-optimizer/aldgate-flats")
        
        assert response.status_code == 200
        data = response.json()
        
        # May have no data or have analysis
        if "error" in data:
            print(f"LOS Optimizer: {data['error']}")
            return
        
        # Verify KPIs
        assert "total_bookings" in data
        assert "avg_los" in data
        assert "avg_rate" in data
        
        # Verify distribution
        assert "distribution" in data
        assert isinstance(data["distribution"], list)
        
        # Verify DOW analysis
        assert "dow_analysis" in data
        assert len(data["dow_analysis"]) == 7  # 7 days of week
        
        # Verify source analysis
        assert "source_analysis" in data
        
        # Verify recommendations
        assert "recommendations" in data
        assert isinstance(data["recommendations"], list)
        
        print(f"LOS Analysis: {data['total_bookings']} bookings, Avg LOS: {data['avg_los']} nights")
        print(f"Recommendations: {len(data['recommendations'])}")
        for rec in data["recommendations"][:3]:
            print(f"  - {rec['type']}: {rec['title']} ({rec['priority']})")
    
    def test_los_optimizer_all_properties(self, auth_session):
        """Test LOS optimizer for all properties"""
        response = auth_session.get(f"{BASE_URL}/api/revenue/los-optimizer/all")
        
        assert response.status_code == 200
        data = response.json()
        
        if "error" not in data:
            assert "total_bookings" in data
            assert "distribution" in data
    
    def test_los_create_restriction(self, auth_session):
        """Test creating LOS restriction"""
        response = auth_session.post(f"{BASE_URL}/api/revenue/los-optimizer/aldgate-flats/restriction", json={
            "type": "min_stay",
            "value": 2,
            "applies_to": "weekends",
            "days": ["Fri", "Sat"],
            "date_from": "2026-04-01",
            "date_to": "2026-06-30",
            "enabled": True
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert "id" in data
        assert data["type"] == "min_stay"
        assert data["value"] == 2
        assert data["property_id"] == "aldgate-flats"
        assert data["enabled"] == True
        print(f"Created LOS restriction: {data['id']}")


class TestMobileCompanion(TestAuth):
    """Mobile Companion API tests"""
    
    def test_mobile_dashboard(self, auth_session):
        """Test mobile dashboard endpoint"""
        response = auth_session.get(f"{BASE_URL}/api/mobile/dashboard/aldgate-flats")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert "date" in data
        assert "property_id" in data
        assert data["property_id"] == "aldgate-flats"
        
        # Verify today's KPIs
        assert "today" in data
        today = data["today"]
        assert "occupancy_pct" in today
        assert "booked_rooms" in today
        assert "total_rooms" in today
        assert "available" in today
        assert "revenue" in today
        assert "adr" in today
        assert "arrivals" in today
        assert "departures" in today
        assert "in_house" in today
        
        # Verify tomorrow preview
        assert "tomorrow" in data
        assert "occupancy_pct" in data["tomorrow"]
        assert "arrivals" in data["tomorrow"]
        
        # Verify action items
        assert "action_items" in data
        actions = data["action_items"]
        assert "unread_notifications" in actions
        assert "pending_reviews" in actions
        assert "dirty_rooms" in actions
        assert "price_alerts" in actions
        
        print(f"Mobile Dashboard: {today['occupancy_pct']}% occupancy, {today['booked_rooms']}/{today['total_rooms']} rooms")
        print(f"Action Items: {actions['dirty_rooms']} dirty rooms, {actions['pending_reviews']} pending reviews")
    
    def test_mobile_dashboard_all_properties(self, auth_session):
        """Test mobile dashboard for all properties"""
        response = auth_session.get(f"{BASE_URL}/api/mobile/dashboard/all")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "today" in data
        assert "action_items" in data
    
    def test_mobile_arrivals(self, auth_session):
        """Test mobile arrivals endpoint"""
        response = auth_session.get(f"{BASE_URL}/api/mobile/arrivals/aldgate-flats")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "date" in data
        assert "count" in data
        assert "guests" in data
        assert isinstance(data["guests"], list)
        
        # If there are arrivals, verify structure
        if data["guests"]:
            guest = data["guests"][0]
            assert "id" in guest
            assert "name" in guest
            assert "nights" in guest
            assert "status" in guest
        
        print(f"Mobile Arrivals: {data['count']} guests arriving today")
    
    def test_mobile_housekeeping(self, auth_session):
        """Test mobile housekeeping endpoint"""
        response = auth_session.get(f"{BASE_URL}/api/mobile/housekeeping/aldgate-flats")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "total" in data
        assert "clean" in data
        assert "dirty" in data
        assert "inspected" in data
        assert "rooms" in data
        
        # Verify rooms breakdown
        rooms = data["rooms"]
        assert "clean" in rooms
        assert "dirty" in rooms
        assert "inspected" in rooms
        
        print(f"Housekeeping: {data['total']} total, {data['clean']} clean, {data['dirty']} dirty, {data['inspected']} inspected")
        
        # Verify dirty rooms have structure
        if data["rooms"]["dirty"]:
            dirty_room = data["rooms"]["dirty"][0]
            assert "id" in dirty_room
            assert "name" in dirty_room
            assert "floor" in dirty_room


class TestUnauthorizedAccess:
    """Test unauthorized access to protected endpoints"""
    
    def test_displacement_analyze_unauthorized(self):
        """Test displacement analyze without auth"""
        response = requests.post(f"{BASE_URL}/api/revenue/displacement/analyze", json={
            "check_in": "2026-04-20",
            "check_out": "2026-04-23",
            "rooms_requested": 5
        })
        assert response.status_code == 401
    
    def test_los_optimizer_unauthorized(self):
        """Test LOS optimizer without auth"""
        response = requests.get(f"{BASE_URL}/api/revenue/los-optimizer/aldgate-flats")
        assert response.status_code == 401
    
    def test_mobile_dashboard_unauthorized(self):
        """Test mobile dashboard without auth"""
        response = requests.get(f"{BASE_URL}/api/mobile/dashboard/aldgate-flats")
        assert response.status_code == 401


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
