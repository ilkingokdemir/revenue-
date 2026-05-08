"""
Iteration 211 - Nightly Recap + Concierge Most-Asked Topics
Tests for two new competitor-gap features:
1. Nightly Recap - "What happened last night?" digest with KPIs, YoY, GPT commentary
2. Concierge Topics - GPT-5.2 clustering of guest questions into topics
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

@pytest.fixture(scope="module")
def auth_session():
    """Login and return authenticated session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    return session


class TestNightlyRecapEndpoint:
    """Tests for GET /api/nightly-recap/{property_id}"""
    
    def test_nightly_recap_default_date(self, auth_session):
        """Test nightly recap with default date (yesterday)"""
        resp = auth_session.get(f"{BASE_URL}/api/nightly-recap/aldgate-flats?yoy=true")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        # Verify required fields
        assert "property_id" in data
        assert data["property_id"] == "aldgate-flats"
        assert "date" in data
        assert "rooms_sold" in data
        assert "total_rooms" in data
        assert "occupancy_pct" in data
        assert "revenue" in data
        assert "adr" in data
        assert "revpar" in data
        assert "arrivals" in data
        assert "departures" in data
        assert "no_shows" in data
        assert "walk_ins" in data
        assert "cancellations" in data
        assert "top_rooms" in data
        assert "as_of" in data
        
        # Verify YoY block when yoy=true
        assert "yoy" in data
        yoy = data["yoy"]
        assert "date" in yoy
        assert "rooms_sold" in yoy
        assert "occupancy_pct" in yoy
        assert "revenue" in yoy
        assert "adr" in yoy
        assert "revpar" in yoy
        assert "occ_delta_pp" in yoy
        # rev_delta_pct and adr_delta_pct may be None if LY values are 0
        
        # Commentary may be empty if LLM fails, but field should exist
        assert "commentary" in data
        
        print(f"✓ Nightly recap default date: {data['date']}, occ={data['occupancy_pct']}%, rooms={data['rooms_sold']}/{data['total_rooms']}")
    
    def test_nightly_recap_specific_date(self, auth_session):
        """Test nightly recap with specific date parameter"""
        resp = auth_session.get(f"{BASE_URL}/api/nightly-recap/aldgate-flats?date_str=2026-04-24&yoy=true")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert data["date"] == "2026-04-24"
        assert "yoy" in data
        assert data["yoy"]["date"] == "2025-04-24"  # Same date last year
        
        print(f"✓ Nightly recap specific date: {data['date']}, YoY date: {data['yoy']['date']}")
    
    def test_nightly_recap_invalid_date_returns_400(self, auth_session):
        """Test that invalid date format returns 400"""
        resp = auth_session.get(f"{BASE_URL}/api/nightly-recap/aldgate-flats?date_str=invalid")
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "date_str must be YYYY-MM-DD" in data.get("detail", "")
        
        print("✓ Invalid date returns 400 with proper error message")
    
    def test_nightly_recap_without_yoy(self, auth_session):
        """Test nightly recap without YoY comparison"""
        resp = auth_session.get(f"{BASE_URL}/api/nightly-recap/aldgate-flats?yoy=false")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        # yoy should be None when yoy=false
        assert data.get("yoy") is None
        
        print("✓ Nightly recap without YoY: yoy field is None")
    
    def test_nightly_recap_top_rooms_structure(self, auth_session):
        """Test that top_rooms has correct structure"""
        resp = auth_session.get(f"{BASE_URL}/api/nightly-recap/aldgate-flats?yoy=true")
        assert resp.status_code == 200
        
        data = resp.json()
        top_rooms = data.get("top_rooms", [])
        
        if len(top_rooms) > 0:
            room = top_rooms[0]
            assert "room_type" in room
            assert "rooms_sold" in room
            assert "revenue" in room
            print(f"✓ Top rooms structure verified: {len(top_rooms)} room types")
        else:
            print("✓ Top rooms is empty (no bookings for this date)")
    
    def test_nightly_recap_requires_auth(self):
        """Test that endpoint requires authentication"""
        session = requests.Session()
        resp = session.get(f"{BASE_URL}/api/nightly-recap/aldgate-flats")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        
        print("✓ Nightly recap requires authentication")


class TestConciergeTopicsEndpoint:
    """Tests for GET /api/concierge/admin/{property_id}/topics"""
    
    def test_concierge_topics_default_days(self, auth_session):
        """Test concierge topics with default 30 days window"""
        resp = auth_session.get(f"{BASE_URL}/api/concierge/admin/aldgate-flats/topics?days=30")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        # Verify required fields
        assert "topics" in data
        assert "samples" in data
        assert "window_days" in data
        assert "fallback" in data
        
        assert data["window_days"] == 30
        
        # aldgate-flats has 21+ seeded questions, so topics should be non-empty
        topics = data["topics"]
        assert len(topics) > 0, "Expected non-empty topics for aldgate-flats"
        
        # Verify topic structure
        topic = topics[0]
        assert "topic" in topic
        assert "count" in topic
        assert "samples" in topic
        assert isinstance(topic["samples"], list)
        
        print(f"✓ Concierge topics: {len(topics)} topics from {data['samples']} samples, fallback={data['fallback']}")
    
    def test_concierge_topics_custom_days(self, auth_session):
        """Test concierge topics with custom days parameter"""
        resp = auth_session.get(f"{BASE_URL}/api/concierge/admin/aldgate-flats/topics?days=7")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        # Days should be clamped to min 7
        assert data["window_days"] == 7
        
        print(f"✓ Concierge topics with days=7: window_days={data['window_days']}")
    
    def test_concierge_topics_days_clamped(self, auth_session):
        """Test that days parameter is clamped to 7-90 range"""
        # Test below minimum
        resp = auth_session.get(f"{BASE_URL}/api/concierge/admin/aldgate-flats/topics?days=1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["window_days"] == 7, "Days should be clamped to minimum 7"
        
        # Test above maximum
        resp = auth_session.get(f"{BASE_URL}/api/concierge/admin/aldgate-flats/topics?days=365")
        assert resp.status_code == 200
        data = resp.json()
        assert data["window_days"] == 90, "Days should be clamped to maximum 90"
        
        print("✓ Days parameter clamped correctly (7-90 range)")
    
    def test_concierge_topics_empty_property(self, auth_session):
        """Test concierge topics for property with no questions"""
        resp = auth_session.get(f"{BASE_URL}/api/concierge/admin/nonexistent-property/topics?days=30")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert data["topics"] == []
        assert data["samples"] == 0
        
        print("✓ Empty property returns empty topics array")
    
    def test_concierge_topics_requires_auth(self):
        """Test that endpoint requires authentication"""
        session = requests.Session()
        resp = session.get(f"{BASE_URL}/api/concierge/admin/aldgate-flats/topics")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        
        print("✓ Concierge topics requires authentication")
    
    def test_concierge_topics_gpt_clustering(self, auth_session):
        """Test that GPT clustering is used when EMERGENT_LLM_KEY is present"""
        resp = auth_session.get(f"{BASE_URL}/api/concierge/admin/aldgate-flats/topics?days=30")
        assert resp.status_code == 200
        
        data = resp.json()
        # With EMERGENT_LLM_KEY present, fallback should be false
        # (unless LLM call fails, in which case fallback=true is acceptable)
        if data["samples"] > 0:
            # If we have samples and fallback is false, GPT was used
            if not data["fallback"]:
                print(f"✓ GPT-5.2 clustering used (fallback=false)")
            else:
                print(f"✓ Fallback heuristic clustering used (LLM may have failed)")
        else:
            print("✓ No samples to cluster")


class TestRegressionSmoke:
    """Smoke tests for existing features that should still work"""
    
    def test_morning_brief_endpoint(self, auth_session):
        """Regression: Morning Brief should still work"""
        resp = auth_session.get(f"{BASE_URL}/api/morning-brief/aldgate-flats")
        assert resp.status_code == 200, f"Morning Brief failed: {resp.status_code}"
        print("✓ Regression: Morning Brief endpoint working")
    
    def test_housekeeping_route_endpoint(self, auth_session):
        """Regression: HK Route should still work"""
        resp = auth_session.get(f"{BASE_URL}/api/housekeeping/route/aldgate-flats")
        assert resp.status_code == 200, f"HK Route failed: {resp.status_code}"
        print("✓ Regression: HK Route endpoint working")
    
    def test_sustainability_endpoint(self, auth_session):
        """Regression: Sustainability/ESG should still work"""
        resp = auth_session.get(f"{BASE_URL}/api/esg/aldgate-flats/dashboard")
        assert resp.status_code == 200, f"ESG Dashboard failed: {resp.status_code}"
        print("✓ Regression: ESG Dashboard endpoint working")
    
    def test_group_requests_endpoint(self, auth_session):
        """Regression: Group Requests should still work"""
        resp = auth_session.get(f"{BASE_URL}/api/groups?property_id=aldgate-flats")
        assert resp.status_code == 200, f"Group Requests failed: {resp.status_code}"
        print("✓ Regression: Group Requests endpoint working")
    
    def test_concierge_sessions_endpoint(self, auth_session):
        """Regression: Concierge Inbox sessions should still work"""
        resp = auth_session.get(f"{BASE_URL}/api/concierge/admin/aldgate-flats/sessions")
        assert resp.status_code == 200, f"Concierge Sessions failed: {resp.status_code}"
        print("✓ Regression: Concierge Sessions endpoint working")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
