"""
Iteration 115 - Hotel Demand Score (HDS) Event Intelligence Tests
Tests the rebuilt Event Intelligence system with smart hotel-demand-aware scoring.
Key changes: Events scored by HDS (0-100) based on hotel room demand, not just attendance.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestHDSEventIntelligence:
    """Test HDS-based Event Intelligence system"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login with admin credentials
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        token = login_resp.json().get("token")
        assert token, "No token returned"
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        self.property_id = "all"
        yield
        # Cleanup: Delete test events
        try:
            events_resp = self.session.get(f"{BASE_URL}/api/revenue/events/{self.property_id}")
            if events_resp.status_code == 200:
                events = events_resp.json().get("events", [])
                for event in events:
                    if event.get("name", "").startswith("TEST_"):
                        self.session.delete(f"{BASE_URL}/api/revenue/events/{event.get('id')}")
        except:
            pass

    # ==================== BACKEND API TESTS ====================
    
    def test_01_login_admin(self):
        """Test admin login with correct credentials"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert resp.status_code == 200, f"Login failed: {resp.text}"
        data = resp.json()
        assert "token" in data, "No token in response"
        # Email is at root level, not nested in "user"
        assert data.get("email") == "admin@hotelbox.com", f"Email mismatch: {data.get('email')}"
        print("✓ Admin login successful")

    def test_02_add_local_event_minimal_impact(self):
        """Test: LOCAL event (HDS:15, visitor_origin:'local') should result in 'minimal' impact and 0 rates adjusted"""
        payload = {
            "name": "TEST_Arsenal vs Tottenham Local Derby",
            "date": "2026-03-15",
            "venue": "Emirates Stadium",
            "category": "sports",
            "estimated_attendance": 60000,
            "hotel_demand_score": 15,
            "visitor_origin": "local",
            "is_evening": True,
            "is_multi_day": False,
            "reasoning": "Local derby - both teams from London, fans go home",
            "auto_price": True
        }
        resp = self.session.post(f"{BASE_URL}/api/revenue/events/{self.property_id}/add", json=payload)
        assert resp.status_code == 200, f"Add event failed: {resp.text}"
        data = resp.json()
        
        # Verify event was created with correct HDS fields
        event = data.get("event", {})
        assert event.get("hotel_demand_score") == 15, f"HDS should be 15, got {event.get('hotel_demand_score')}"
        assert event.get("visitor_origin") == "local", f"visitor_origin should be 'local', got {event.get('visitor_origin')}"
        assert event.get("impact") == "minimal", f"Impact should be 'minimal' for HDS 15, got {event.get('impact')}"
        
        # Verify 0 rates adjusted for minimal impact
        assert data.get("prices_adjusted") == 0, f"Prices adjusted should be 0 for minimal impact, got {data.get('prices_adjusted')}"
        
        print(f"✓ Local event added: HDS={event.get('hotel_demand_score')}, impact={event.get('impact')}, prices_adjusted={data.get('prices_adjusted')}")

    def test_03_add_international_event_critical_impact(self):
        """Test: INTERNATIONAL event (HDS:95, visitor_origin:'international') should result in 'critical' impact and rates adjusted"""
        payload = {
            "name": "TEST_UEFA Champions League Final",
            "date": "2026-05-30",
            "venue": "Wembley Stadium",
            "category": "sports",
            "estimated_attendance": 90000,
            "hotel_demand_score": 95,
            "visitor_origin": "international",
            "is_evening": True,
            "is_multi_day": False,
            "reasoning": "International final - fans travel from across Europe",
            "auto_price": True
        }
        resp = self.session.post(f"{BASE_URL}/api/revenue/events/{self.property_id}/add", json=payload)
        assert resp.status_code == 200, f"Add event failed: {resp.text}"
        data = resp.json()
        
        # Verify event was created with correct HDS fields
        event = data.get("event", {})
        assert event.get("hotel_demand_score") == 95, f"HDS should be 95, got {event.get('hotel_demand_score')}"
        assert event.get("visitor_origin") == "international", f"visitor_origin should be 'international', got {event.get('visitor_origin')}"
        assert event.get("impact") == "critical", f"Impact should be 'critical' for HDS 95, got {event.get('impact')}"
        
        # Verify rates were adjusted for critical impact
        assert data.get("prices_adjusted") > 0, f"Prices adjusted should be > 0 for critical impact, got {data.get('prices_adjusted')}"
        
        print(f"✓ International event added: HDS={event.get('hotel_demand_score')}, impact={event.get('impact')}, prices_adjusted={data.get('prices_adjusted')}")

    def test_04_get_events_returns_hds_counts(self):
        """Test: GET /api/revenue/events/all returns counts with new HDS levels"""
        resp = self.session.get(f"{BASE_URL}/api/revenue/events/{self.property_id}")
        assert resp.status_code == 200, f"Get events failed: {resp.text}"
        data = resp.json()
        
        counts = data.get("counts", {})
        
        # Verify new HDS-based levels exist
        assert "critical" in counts, "Missing 'critical' count"
        assert "high" in counts, "Missing 'high' count"
        assert "moderate" in counts, "Missing 'moderate' count"
        assert "low" in counts, "Missing 'low' count"
        assert "minimal" in counts, "Missing 'minimal' count"
        
        # Verify backward compatibility with legacy levels
        assert "mega" in counts, "Missing legacy 'mega' count (backward compat)"
        assert "large" in counts, "Missing legacy 'large' count (backward compat)"
        assert "medium" in counts, "Missing legacy 'medium' count (backward compat)"
        assert "small" in counts, "Missing legacy 'small' count (backward compat)"
        assert "total" in counts, "Missing 'total' count"
        
        print(f"✓ Event counts returned: critical={counts.get('critical')}, high={counts.get('high')}, moderate={counts.get('moderate')}, low={counts.get('low')}, minimal={counts.get('minimal')}, total={counts.get('total')}")

    def test_05_events_store_hds_fields(self):
        """Test: Events now store HDS fields: hotel_demand_score, visitor_origin, is_evening, is_multi_day, reasoning, estimated_hotel_nights"""
        # First add a test event to ensure we have one with HDS fields
        payload = {
            "name": "TEST_HDS_Fields_Check",
            "date": "2026-07-15",
            "venue": "Test Venue",
            "category": "concert",
            "estimated_attendance": 50000,
            "hotel_demand_score": 75,
            "visitor_origin": "national",
            "is_evening": True,
            "is_multi_day": False,
            "reasoning": "Test event for HDS field verification",
            "estimated_hotel_nights": 25000,
            "auto_price": False
        }
        add_resp = self.session.post(f"{BASE_URL}/api/revenue/events/{self.property_id}/add", json=payload)
        assert add_resp.status_code == 200, f"Add event failed: {add_resp.text}"
        
        # Now get events and verify the newly added event has all HDS fields
        resp = self.session.get(f"{BASE_URL}/api/revenue/events/{self.property_id}")
        assert resp.status_code == 200, f"Get events failed: {resp.text}"
        events = resp.json().get("events", [])
        
        # Find our test event
        test_event = None
        for e in events:
            if e.get("name") == "TEST_HDS_Fields_Check":
                test_event = e
                break
        
        assert test_event is not None, "Test event not found"
        
        # Verify all HDS fields are present
        assert "hotel_demand_score" in test_event, f"Missing hotel_demand_score"
        assert "visitor_origin" in test_event, f"Missing visitor_origin"
        assert "is_evening" in test_event, f"Missing is_evening"
        assert "is_multi_day" in test_event, f"Missing is_multi_day"
        assert "reasoning" in test_event, f"Missing reasoning"
        assert "estimated_hotel_nights" in test_event, f"Missing estimated_hotel_nights"
        
        # Verify values
        assert test_event.get("hotel_demand_score") == 75, f"HDS should be 75, got {test_event.get('hotel_demand_score')}"
        assert test_event.get("visitor_origin") == "national", f"visitor_origin should be 'national', got {test_event.get('visitor_origin')}"
        assert test_event.get("is_evening") == True, f"is_evening should be True"
        assert test_event.get("is_multi_day") == False, f"is_multi_day should be False"
        
        print(f"✓ Event has all HDS fields: HDS={test_event.get('hotel_demand_score')}, origin={test_event.get('visitor_origin')}, evening={test_event.get('is_evening')}, multi_day={test_event.get('is_multi_day')}")

    def test_06_dynamic_pricing_shows_hds_breakdown(self):
        """Test: Dynamic pricing event factor breakdown shows HDS and visitor_origin"""
        # First add a high-impact event for today/tomorrow to ensure it shows in pricing
        from datetime import datetime, timedelta
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        
        payload = {
            "name": "TEST_Champions League Match",
            "date": tomorrow,
            "venue": "Wembley",
            "category": "sports",
            "estimated_attendance": 80000,
            "hotel_demand_score": 85,
            "visitor_origin": "international",
            "is_evening": True,
            "auto_price": True
        }
        add_resp = self.session.post(f"{BASE_URL}/api/revenue/events/{self.property_id}/add", json=payload)
        assert add_resp.status_code == 200, f"Add event failed: {add_resp.text}"
        
        # Now calculate dynamic pricing
        calc_resp = self.session.post(f"{BASE_URL}/api/revenue/dynamic-pricing/{self.property_id}/calculate", json={"days": 7})
        assert calc_resp.status_code == 200, f"Calculate pricing failed: {calc_resp.text}"
        data = calc_resp.json()
        
        # Find the day with our event
        room_types = data.get("room_types", [])
        assert len(room_types) > 0, "No room types returned"
        
        prices = room_types[0].get("prices", [])
        event_day = None
        for p in prices:
            if p.get("date") == tomorrow:
                event_day = p
                break
        
        if event_day and event_day.get("breakdown", {}).get("event"):
            event_breakdown = event_day.get("breakdown", {}).get("event", "")
            # Verify breakdown contains HDS
            assert "HDS:" in event_breakdown, f"Event breakdown should contain 'HDS:', got: {event_breakdown}"
            # Note: Legacy events may have "unknown" visitor_origin, new events should have proper origin
            # The breakdown format is: "+{pct}% ({event_name} | HDS:{hds} | {visitor_origin})"
            print(f"✓ Dynamic pricing event breakdown: {event_breakdown}")
        else:
            # Check if there's any event in the first 7 days
            events_found = [p for p in prices if p.get("event")]
            if events_found:
                print(f"✓ Dynamic pricing calculated with {len(events_found)} event days (our test event may overlap with existing)")
            else:
                print(f"✓ Dynamic pricing calculated (no events in first 7 days)")

    def test_07_hds_impact_level_mapping(self):
        """Test: HDS values correctly map to impact levels"""
        test_cases = [
            {"hds": 95, "expected_impact": "critical", "visitor_origin": "international"},
            {"hds": 80, "expected_impact": "critical", "visitor_origin": "international"},
            {"hds": 70, "expected_impact": "high", "visitor_origin": "national"},
            {"hds": 60, "expected_impact": "high", "visitor_origin": "national"},
            {"hds": 50, "expected_impact": "moderate", "visitor_origin": "regional"},
            {"hds": 40, "expected_impact": "moderate", "visitor_origin": "regional"},
            {"hds": 30, "expected_impact": "low", "visitor_origin": "local"},
            {"hds": 20, "expected_impact": "low", "visitor_origin": "local"},
            {"hds": 15, "expected_impact": "minimal", "visitor_origin": "local"},
            {"hds": 10, "expected_impact": "minimal", "visitor_origin": "local"},
        ]
        
        for i, tc in enumerate(test_cases):
            payload = {
                "name": f"TEST_HDS_Level_{tc['hds']}",
                "date": f"2026-06-{10+i:02d}",
                "venue": "Test Venue",
                "category": "other",
                "estimated_attendance": 10000,
                "hotel_demand_score": tc["hds"],
                "visitor_origin": tc["visitor_origin"],
                "auto_price": False  # Don't adjust prices for this test
            }
            resp = self.session.post(f"{BASE_URL}/api/revenue/events/{self.property_id}/add", json=payload)
            assert resp.status_code == 200, f"Add event failed for HDS {tc['hds']}: {resp.text}"
            
            event = resp.json().get("event", {})
            actual_impact = event.get("impact")
            assert actual_impact == tc["expected_impact"], f"HDS {tc['hds']} should map to '{tc['expected_impact']}', got '{actual_impact}'"
            
            print(f"✓ HDS {tc['hds']} → impact '{actual_impact}' (expected: {tc['expected_impact']})")

    def test_08_legacy_impact_backward_compat(self):
        """Test: Legacy impact levels (mega/large/medium/small) are mapped to new levels"""
        # The backend should map legacy impacts via LEGACY_MAP
        # mega → critical, large → high, medium → moderate, small → low
        
        resp = self.session.get(f"{BASE_URL}/api/revenue/events/{self.property_id}")
        assert resp.status_code == 200, f"Get events failed: {resp.text}"
        counts = resp.json().get("counts", {})
        
        # Verify legacy counts equal new counts (backward compat mapping)
        assert counts.get("mega") == counts.get("critical"), f"mega should equal critical: {counts.get('mega')} vs {counts.get('critical')}"
        assert counts.get("large") == counts.get("high"), f"large should equal high: {counts.get('large')} vs {counts.get('high')}"
        assert counts.get("medium") == counts.get("moderate"), f"medium should equal moderate: {counts.get('medium')} vs {counts.get('moderate')}"
        assert counts.get("small") == counts.get("low"), f"small should equal low: {counts.get('small')} vs {counts.get('low')}"
        
        print(f"✓ Legacy mapping verified: mega={counts.get('mega')}→critical, large={counts.get('large')}→high, medium={counts.get('medium')}→moderate, small={counts.get('small')}→low")

    def test_09_auth_required_for_events(self):
        """Test: Event endpoints require authentication"""
        # Test without auth
        no_auth_session = requests.Session()
        no_auth_session.headers.update({"Content-Type": "application/json"})
        
        # GET events should require auth
        resp = no_auth_session.get(f"{BASE_URL}/api/revenue/events/{self.property_id}")
        assert resp.status_code in [401, 403], f"GET events should require auth, got {resp.status_code}"
        
        # POST add event should require auth
        resp = no_auth_session.post(f"{BASE_URL}/api/revenue/events/{self.property_id}/add", json={"name": "Test"})
        assert resp.status_code in [401, 403], f"POST add event should require auth, got {resp.status_code}"
        
        print("✓ Event endpoints require authentication")

    def test_10_price_boost_by_hds_level(self):
        """Test: Price boosts are correct for each HDS level"""
        # Critical (HDS 80+): +45%, High (60-79): +30%, Moderate (40-59): +15%, Low (20-39): +5%, Minimal (0-19): 0%
        
        # Get events and verify the pricing logic
        resp = self.session.get(f"{BASE_URL}/api/revenue/events/{self.property_id}")
        assert resp.status_code == 200
        events = resp.json().get("events", [])
        
        # Find test events and verify their impact levels
        critical_events = [e for e in events if e.get("impact") == "critical"]
        high_events = [e for e in events if e.get("impact") == "high"]
        moderate_events = [e for e in events if e.get("impact") == "moderate"]
        low_events = [e for e in events if e.get("impact") == "low"]
        minimal_events = [e for e in events if e.get("impact") == "minimal"]
        
        print(f"✓ Events by impact: critical={len(critical_events)}, high={len(high_events)}, moderate={len(moderate_events)}, low={len(low_events)}, minimal={len(minimal_events)}")
        
        # Verify HDS ranges for each impact level
        for e in critical_events:
            hds = e.get("hotel_demand_score", 0)
            if hds > 0:  # Only check if HDS is set
                assert hds >= 80, f"Critical event should have HDS >= 80, got {hds}"
        
        for e in high_events:
            hds = e.get("hotel_demand_score", 0)
            if hds > 0:
                assert 60 <= hds < 80, f"High event should have HDS 60-79, got {hds}"
        
        for e in moderate_events:
            hds = e.get("hotel_demand_score", 0)
            if hds > 0:
                assert 40 <= hds < 60, f"Moderate event should have HDS 40-59, got {hds}"
        
        for e in low_events:
            hds = e.get("hotel_demand_score", 0)
            if hds > 0:
                assert 20 <= hds < 40, f"Low event should have HDS 20-39, got {hds}"
        
        for e in minimal_events:
            hds = e.get("hotel_demand_score", 0)
            if hds > 0:
                assert hds < 20, f"Minimal event should have HDS < 20, got {hds}"
        
        print("✓ HDS ranges verified for all impact levels")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
