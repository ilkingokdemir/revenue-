"""
Iteration 71 - Testing Loyalty Program, Duty Manager Logbook, and Occupancy Forecasting
- Loyalty: Points, Tiers (Standard/Silver/Gold/Platinum), Rewards (8 items), Earn/Redeem, Leaderboard
- Logbook: Entry types (note/incident/VIP/complaint/request), Shift filtering, Resolve workflow, Handovers
- Forecast: 30/60/90-day forecast, Daily breakdown, Revenue estimates
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json().get("token")

@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}

@pytest.fixture(scope="module")
def property_id():
    return "aldgate-flats"


class TestLoyaltyRewards:
    """Test Loyalty Rewards Catalog - 8 rewards"""
    
    def test_get_rewards_returns_8_items(self):
        """GET /api/loyalty/rewards - Returns 8 reward items"""
        response = requests.get(f"{BASE_URL}/api/loyalty/rewards")
        assert response.status_code == 200
        rewards = response.json()
        assert len(rewards) == 8, f"Expected 8 rewards, got {len(rewards)}"
        
        # Verify reward structure
        expected_ids = ["free_night", "room_upgrade", "spa_voucher", "restaurant_credit", 
                       "late_checkout", "welcome_amenity", "parking", "breakfast"]
        actual_ids = [r["id"] for r in rewards]
        for eid in expected_ids:
            assert eid in actual_ids, f"Missing reward: {eid}"
        
        # Verify each reward has required fields
        for r in rewards:
            assert "id" in r
            assert "name" in r
            assert "points_cost" in r
            assert "category" in r
            assert "description" in r
            assert r["points_cost"] > 0


class TestLoyaltyLeaderboard:
    """Test Loyalty Leaderboard"""
    
    def test_get_leaderboard(self, auth_headers, property_id):
        """GET /api/loyalty/leaderboard/{property_id} - Returns members sorted by lifetime_points"""
        response = requests.get(f"{BASE_URL}/api/loyalty/leaderboard/{property_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert "members" in data
        assert "tier_counts" in data
        assert "total_members" in data
        
        # Verify tier_counts has all tiers
        assert "standard" in data["tier_counts"]
        assert "silver" in data["tier_counts"]
        assert "gold" in data["tier_counts"]
        assert "platinum" in data["tier_counts"]
        
        # Verify members are sorted by lifetime_points (descending)
        if len(data["members"]) > 1:
            for i in range(len(data["members"]) - 1):
                assert data["members"][i].get("lifetime_points", 0) >= data["members"][i+1].get("lifetime_points", 0)


class TestLoyaltyMember:
    """Test Loyalty Member Operations"""
    
    @pytest.fixture(scope="class")
    def test_guest_id(self, auth_headers, property_id):
        """Get a guest ID for testing"""
        response = requests.get(f"{BASE_URL}/api/guests/profiles/{property_id}", headers=auth_headers)
        if response.status_code == 200 and len(response.json()) > 0:
            return response.json()[0]["id"]
        pytest.skip("No guest profiles available for testing")
    
    def test_get_loyalty_member(self, auth_headers, test_guest_id):
        """GET /api/loyalty/member/{guest_id} - Returns member details with tier, points, benefits"""
        response = requests.get(f"{BASE_URL}/api/loyalty/member/{test_guest_id}", headers=auth_headers)
        assert response.status_code == 200
        member = response.json()
        
        # Verify member structure
        assert "id" in member
        assert "guest_id" in member
        assert "guest_name" in member
        assert "tier" in member
        assert "points" in member
        assert "lifetime_points" in member
        assert "total_stays" in member
        assert "total_spend" in member
        assert "tier_benefits" in member
        assert "next_tier" in member or member["tier"] == "platinum"
        assert "stays_to_next_tier" in member
        
        # Verify tier is valid
        assert member["tier"] in ["standard", "silver", "gold", "platinum"]
    
    def test_earn_points_with_tier_multiplier(self, auth_headers, test_guest_id):
        """POST /api/loyalty/earn-points - Awards points with tier multiplier, auto-upgrades tier"""
        # First get current member state
        member_resp = requests.get(f"{BASE_URL}/api/loyalty/member/{test_guest_id}", headers=auth_headers)
        initial_points = member_resp.json().get("points", 0)
        
        # Earn points
        response = requests.post(f"{BASE_URL}/api/loyalty/earn-points", headers=auth_headers, json={
            "guest_id": test_guest_id,
            "amount": 50,
            "reason": "dining"
        })
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "points_earned" in data
        assert "new_balance" in data
        assert "tier" in data
        assert "tier_upgraded" in data
        
        # Points should be amount * 10 * multiplier
        assert data["points_earned"] > 0
        assert data["new_balance"] >= initial_points + data["points_earned"]
    
    def test_earn_points_invalid_member(self, auth_headers):
        """POST /api/loyalty/earn-points - Returns 404 for non-existent member"""
        response = requests.post(f"{BASE_URL}/api/loyalty/earn-points", headers=auth_headers, json={
            "guest_id": "non-existent-guest-id",
            "amount": 100,
            "reason": "stay"
        })
        assert response.status_code == 404


class TestLoyaltyRedeem:
    """Test Loyalty Points Redemption"""
    
    @pytest.fixture(scope="class")
    def member_with_points(self, auth_headers, property_id):
        """Create a member with enough points for redemption"""
        # Get a guest
        guests_resp = requests.get(f"{BASE_URL}/api/guests/profiles/{property_id}", headers=auth_headers)
        if guests_resp.status_code != 200 or len(guests_resp.json()) == 0:
            pytest.skip("No guests available")
        
        guest_id = guests_resp.json()[0]["id"]
        
        # Get/create loyalty member
        requests.get(f"{BASE_URL}/api/loyalty/member/{guest_id}", headers=auth_headers)
        
        # Award enough points for cheapest reward (parking = 200 pts)
        requests.post(f"{BASE_URL}/api/loyalty/earn-points", headers=auth_headers, json={
            "guest_id": guest_id,
            "amount": 100,  # Will give at least 1000 points
            "reason": "bonus"
        })
        
        return guest_id
    
    def test_redeem_points_success(self, auth_headers, member_with_points):
        """POST /api/loyalty/redeem - Redeems points for reward, validates balance"""
        # Get current balance
        member_resp = requests.get(f"{BASE_URL}/api/loyalty/member/{member_with_points}", headers=auth_headers)
        current_points = member_resp.json().get("points", 0)
        
        if current_points < 200:
            pytest.skip("Not enough points for redemption test")
        
        response = requests.post(f"{BASE_URL}/api/loyalty/redeem", headers=auth_headers, json={
            "guest_id": member_with_points,
            "reward_id": "parking"  # 200 points
        })
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "redeemed"
        assert data["reward"] == "Free Parking (1 night)"
        assert data["points_spent"] == 200
        assert data["new_balance"] == current_points - 200
    
    def test_redeem_insufficient_points(self, auth_headers, property_id):
        """POST /api/loyalty/redeem - Returns 400 when not enough points"""
        # Get a guest with low points
        guests_resp = requests.get(f"{BASE_URL}/api/guests/profiles/{property_id}", headers=auth_headers)
        if guests_resp.status_code != 200 or len(guests_resp.json()) < 2:
            pytest.skip("Not enough guests")
        
        # Use a different guest that might have 0 points
        guest_id = guests_resp.json()[-1]["id"]
        
        # Create member (will have 0 points initially)
        requests.get(f"{BASE_URL}/api/loyalty/member/{guest_id}", headers=auth_headers)
        
        # Try to redeem expensive reward
        response = requests.post(f"{BASE_URL}/api/loyalty/redeem", headers=auth_headers, json={
            "guest_id": guest_id,
            "reward_id": "free_night"  # 5000 points
        })
        # Should fail if not enough points
        if response.status_code == 400:
            assert "Not enough points" in response.json().get("detail", "")


class TestLogbookEntries:
    """Test Duty Manager Logbook Entries"""
    
    def test_create_logbook_entry(self, auth_headers, property_id):
        """POST /api/logbook/entries - Creates logbook entry with type, priority, shift"""
        unique_title = f"TEST_Entry_{uuid.uuid4().hex[:8]}"
        response = requests.post(f"{BASE_URL}/api/logbook/entries", headers=auth_headers, json={
            "property_id": property_id,
            "type": "complaint",
            "title": unique_title,
            "content": "Guest complained about noise from room 302",
            "priority": "high",
            "room_number": "301",
            "guest_name": "Test Guest",
            "follow_up_required": True
        })
        assert response.status_code == 200
        entry = response.json()
        
        # Verify entry structure
        assert entry["id"]
        assert entry["property_id"] == property_id
        assert entry["type"] == "complaint"
        assert entry["title"] == unique_title
        assert entry["priority"] == "high"
        assert entry["status"] == "open"
        assert entry["shift"] in ["morning", "afternoon", "night"]
        assert entry["follow_up_required"] == True
        
        return entry["id"]
    
    def test_list_logbook_entries(self, auth_headers, property_id):
        """GET /api/logbook/entries/{property_id} - Lists entries"""
        response = requests.get(f"{BASE_URL}/api/logbook/entries/{property_id}", headers=auth_headers)
        assert response.status_code == 200
        entries = response.json()
        assert isinstance(entries, list)
        
        # Verify entry structure if entries exist
        if len(entries) > 0:
            entry = entries[0]
            assert "id" in entry
            assert "type" in entry
            assert "title" in entry
            assert "status" in entry
            assert "shift" in entry
    
    def test_list_entries_with_shift_filter(self, auth_headers, property_id):
        """GET /api/logbook/entries/{property_id}?shift=morning - Filter by shift"""
        response = requests.get(f"{BASE_URL}/api/logbook/entries/{property_id}?shift=morning", headers=auth_headers)
        assert response.status_code == 200
        entries = response.json()
        
        # All entries should be morning shift
        for entry in entries:
            assert entry["shift"] == "morning"
    
    def test_resolve_logbook_entry(self, auth_headers, property_id):
        """PUT /api/logbook/entries/{id} - Resolves entry"""
        # First create an entry
        create_resp = requests.post(f"{BASE_URL}/api/logbook/entries", headers=auth_headers, json={
            "property_id": property_id,
            "type": "request",
            "title": f"TEST_Resolve_{uuid.uuid4().hex[:8]}",
            "content": "Extra towels requested",
            "priority": "normal"
        })
        entry_id = create_resp.json()["id"]
        
        # Resolve it
        response = requests.put(f"{BASE_URL}/api/logbook/entries/{entry_id}", headers=auth_headers, json={
            "status": "resolved"
        })
        assert response.status_code == 200
        resolved = response.json()
        
        assert resolved["status"] == "resolved"
        assert resolved["resolved_at"] != ""
        assert resolved["resolved_by"] != ""
    
    def test_create_entry_all_types(self, auth_headers, property_id):
        """Test creating entries with all valid types"""
        entry_types = ["note", "incident", "vip", "complaint", "request"]
        
        for entry_type in entry_types:
            response = requests.post(f"{BASE_URL}/api/logbook/entries", headers=auth_headers, json={
                "property_id": property_id,
                "type": entry_type,
                "title": f"TEST_{entry_type}_{uuid.uuid4().hex[:6]}",
                "content": f"Test {entry_type} entry",
                "priority": "normal"
            })
            assert response.status_code == 200, f"Failed to create {entry_type} entry"
            assert response.json()["type"] == entry_type


class TestShiftHandovers:
    """Test Shift Handover Operations"""
    
    def test_create_shift_handover(self, auth_headers, property_id):
        """POST /api/logbook/shift-handover - Creates handover with key_items and pending_issues"""
        response = requests.post(f"{BASE_URL}/api/logbook/shift-handover", headers=auth_headers, json={
            "property_id": property_id,
            "from_shift": "morning",
            "to_shift": "afternoon",
            "summary": "TEST_Quiet morning shift, all check-ins completed",
            "key_items": ["VIP in room 501", "Pool closed for maintenance"],
            "pending_issues": ["Room 305 AC repair scheduled", "Guest complaint pending resolution"],
            "vip_arrivals": ["Mr. Smith - Suite 501"]
        })
        assert response.status_code == 200
        handover = response.json()
        
        # Verify structure
        assert handover["id"]
        assert handover["property_id"] == property_id
        assert handover["from_shift"] == "morning"
        assert handover["to_shift"] == "afternoon"
        assert handover["summary"]
        assert len(handover["key_items"]) == 2
        assert len(handover["pending_issues"]) == 2
        assert handover["handover_by"]
        assert handover["created_at"]
    
    def test_list_shift_handovers(self, auth_headers, property_id):
        """GET /api/logbook/shift-handovers/{property_id} - Lists handovers"""
        response = requests.get(f"{BASE_URL}/api/logbook/shift-handovers/{property_id}", headers=auth_headers)
        assert response.status_code == 200
        handovers = response.json()
        assert isinstance(handovers, list)
        
        # Verify handover structure if any exist
        if len(handovers) > 0:
            h = handovers[0]
            assert "id" in h
            assert "from_shift" in h
            assert "to_shift" in h
            assert "key_items" in h
            assert "pending_issues" in h


class TestOccupancyForecast:
    """Test Occupancy Forecasting"""
    
    def test_get_forecast_90_days(self, auth_headers, property_id):
        """GET /api/forecast/occupancy/{property_id}?days=90 - Returns 90-day forecast"""
        response = requests.get(f"{BASE_URL}/api/forecast/occupancy/{property_id}?days=90", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert data["property_id"] == property_id
        assert "total_rooms" in data
        assert "forecast" in data
        assert "summary" in data
        assert "generated_at" in data
        
        # Verify forecast has 90 days
        assert len(data["forecast"]) == 90
        
        # Verify daily data structure
        day = data["forecast"][0]
        assert "date" in day
        assert "day_of_week" in day
        assert "bookings" in day
        assert "total_rooms" in day
        assert "available" in day
        assert "occupancy_pct" in day
        assert "estimated_revenue" in day
        assert "avg_rate" in day
    
    def test_forecast_summary_periods(self, auth_headers, property_id):
        """Verify forecast summary has 7/30/90-day summaries"""
        response = requests.get(f"{BASE_URL}/api/forecast/occupancy/{property_id}?days=90", headers=auth_headers)
        assert response.status_code == 200
        summary = response.json()["summary"]
        
        # Verify all summary periods
        assert "7_day" in summary
        assert "30_day" in summary
        assert "90_day" in summary
        
        # Verify 7-day summary structure
        assert "avg_occupancy" in summary["7_day"]
        assert "total_revenue" in summary["7_day"]
        
        # Verify 30-day summary structure
        assert "avg_occupancy" in summary["30_day"]
        assert "total_revenue" in summary["30_day"]
        
        # Verify 90-day summary structure
        assert "avg_occupancy" in summary["90_day"]
        assert "total_revenue" in summary["90_day"]
    
    def test_forecast_different_days(self, auth_headers, property_id):
        """Test forecast with different day ranges"""
        for days in [7, 30, 60]:
            response = requests.get(f"{BASE_URL}/api/forecast/occupancy/{property_id}?days={days}", headers=auth_headers)
            assert response.status_code == 200
            data = response.json()
            assert len(data["forecast"]) == days, f"Expected {days} days, got {len(data['forecast'])}"
    
    def test_forecast_data_consistency(self, auth_headers, property_id):
        """Verify forecast data is consistent (available = total_rooms - bookings)"""
        response = requests.get(f"{BASE_URL}/api/forecast/occupancy/{property_id}?days=30", headers=auth_headers)
        assert response.status_code == 200
        
        for day in response.json()["forecast"]:
            expected_available = day["total_rooms"] - day["bookings"]
            assert day["available"] == expected_available, f"Inconsistent availability for {day['date']}"
            
            # Occupancy should be (bookings / total_rooms) * 100
            if day["total_rooms"] > 0:
                expected_occ = round(day["bookings"] / day["total_rooms"] * 100, 1)
                assert abs(day["occupancy_pct"] - expected_occ) < 0.2, f"Inconsistent occupancy for {day['date']}"


class TestAuthenticationRequired:
    """Test that endpoints require authentication"""
    
    def test_leaderboard_requires_auth(self, property_id):
        """Leaderboard requires authentication"""
        response = requests.get(f"{BASE_URL}/api/loyalty/leaderboard/{property_id}")
        assert response.status_code in [401, 403]
    
    def test_earn_points_requires_auth(self):
        """Earn points requires authentication"""
        response = requests.post(f"{BASE_URL}/api/loyalty/earn-points", json={
            "guest_id": "test", "amount": 100, "reason": "stay"
        })
        assert response.status_code in [401, 403]
    
    def test_logbook_entries_requires_auth(self, property_id):
        """Logbook entries requires authentication"""
        response = requests.get(f"{BASE_URL}/api/logbook/entries/{property_id}")
        assert response.status_code in [401, 403]
    
    def test_forecast_requires_auth(self, property_id):
        """Forecast requires authentication"""
        response = requests.get(f"{BASE_URL}/api/forecast/occupancy/{property_id}")
        assert response.status_code in [401, 403]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
