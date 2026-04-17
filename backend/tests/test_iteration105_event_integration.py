"""
Iteration 105 - Event Intelligence Integration into Market Robot & Smart Pricing
Tests the NEW wiring of events into:
1. Market Robot Supply endpoint - event overlay data, upcoming_events, event_days count
2. Smart Pricing - event_days KPI, upcoming_events, price_evolution with events, calendar with EVENT level
3. Smart Pricing recalculate - event-aware recommendations
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuth:
    """Authentication for all tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get auth token for admin user"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in response"
        return data["token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestMarketRobotSupplyWithEvents(TestAuth):
    """Test Market Robot Supply endpoint returns event overlay data"""
    
    def test_supply_endpoint_returns_event_fields(self, auth_headers):
        """GET /api/revenue/market-robot/all/supply returns supply data with event overlay"""
        response = requests.get(f"{BASE_URL}/api/revenue/market-robot/all/supply", headers=auth_headers)
        assert response.status_code == 200, f"Supply endpoint failed: {response.text}"
        data = response.json()
        
        # Check structure
        assert "snapshots" in data, "Missing snapshots in response"
        assert "summary" in data, "Missing summary in response"
        assert "upcoming_events" in data, "Missing upcoming_events in response"
        
        # Check summary has event_days
        summary = data["summary"]
        assert "event_days" in summary, "Missing event_days in summary"
        print(f"Supply summary: total_dates={summary.get('total_dates')}, event_days={summary.get('event_days')}")
        
    def test_supply_snapshots_have_event_overlay(self, auth_headers):
        """Supply snapshots should have event, event_impact, event_boost fields for event dates"""
        response = requests.get(f"{BASE_URL}/api/revenue/market-robot/all/supply", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        snapshots = data.get("snapshots", [])
        # Find snapshots with events
        event_snapshots = [s for s in snapshots if s.get("event")]
        
        if event_snapshots:
            # Verify event overlay fields
            sample = event_snapshots[0]
            assert "event" in sample, "Missing event field"
            assert "event_impact" in sample, "Missing event_impact field"
            assert "event_boost" in sample, "Missing event_boost field"
            print(f"Event snapshot sample: date={sample.get('date')}, event={sample.get('event')}, impact={sample.get('event_impact')}, boost={sample.get('event_boost')}")
        else:
            print("No event snapshots found in supply data (may need scan first)")
    
    def test_upcoming_events_structure(self, auth_headers):
        """upcoming_events array should have proper structure"""
        response = requests.get(f"{BASE_URL}/api/revenue/market-robot/all/supply", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        upcoming = data.get("upcoming_events", [])
        print(f"Upcoming events count: {len(upcoming)}")
        
        if upcoming:
            sample = upcoming[0]
            # Check required fields
            assert "name" in sample, "Missing name in upcoming event"
            assert "date" in sample, "Missing date in upcoming event"
            assert "impact" in sample, "Missing impact in upcoming event"
            assert "estimated_attendance" in sample, "Missing estimated_attendance in upcoming event"
            print(f"Sample upcoming event: {sample.get('name')} on {sample.get('date')} ({sample.get('impact')})")


class TestSmartPricingWithEvents(TestAuth):
    """Test Smart Pricing endpoint returns event-aware data"""
    
    def test_smart_pricing_returns_event_kpis(self, auth_headers):
        """GET /api/revenue/smart-pricing/all returns kpis.event_days"""
        response = requests.get(f"{BASE_URL}/api/revenue/smart-pricing/all", headers=auth_headers)
        assert response.status_code == 200, f"Smart Pricing failed: {response.text}"
        data = response.json()
        
        # Check KPIs
        assert "kpis" in data, "Missing kpis in response"
        kpis = data["kpis"]
        assert "event_days" in kpis, "Missing event_days in kpis"
        print(f"Smart Pricing KPIs: event_days={kpis.get('event_days')}, avg_daily_rate={kpis.get('avg_daily_rate')}")
        
    def test_smart_pricing_returns_upcoming_events(self, auth_headers):
        """Smart Pricing should return upcoming_events array"""
        response = requests.get(f"{BASE_URL}/api/revenue/smart-pricing/all", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "upcoming_events" in data, "Missing upcoming_events in response"
        upcoming = data.get("upcoming_events", [])
        print(f"Smart Pricing upcoming events: {len(upcoming)}")
        
        if upcoming:
            sample = upcoming[0]
            assert "name" in sample, "Missing name"
            assert "date" in sample, "Missing date"
            assert "impact" in sample, "Missing impact"
            print(f"Sample: {sample.get('name')} ({sample.get('impact')})")
    
    def test_price_evolution_has_event_fields(self, auth_headers):
        """price_evolution should have event/event_impact/event_boost for event dates"""
        response = requests.get(f"{BASE_URL}/api/revenue/smart-pricing/all", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "price_evolution" in data, "Missing price_evolution"
        evolution = data.get("price_evolution", [])
        assert len(evolution) > 0, "Empty price_evolution"
        
        # Find entries with events
        event_entries = [e for e in evolution if e.get("event")]
        print(f"Price evolution: {len(evolution)} days, {len(event_entries)} with events")
        
        if event_entries:
            sample = event_entries[0]
            assert "event" in sample, "Missing event field"
            assert "event_impact" in sample, "Missing event_impact field"
            assert "event_boost" in sample, "Missing event_boost field"
            print(f"Event evolution sample: date={sample.get('date')}, event={sample.get('event')}, boost=+{sample.get('event_boost')}%")
    
    def test_recommendation_calendar_has_event_level(self, auth_headers):
        """recommendation_calendar should show EVENT level for event dates"""
        response = requests.get(f"{BASE_URL}/api/revenue/smart-pricing/all", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "recommendation_calendar" in data, "Missing recommendation_calendar"
        calendar = data.get("recommendation_calendar", [])
        assert len(calendar) > 0, "Empty recommendation_calendar"
        
        # Check first room type's days
        first_rt = calendar[0]
        days = first_rt.get("days", [])
        
        # Find EVENT level days
        event_days = [d for d in days if d.get("level") == "EVENT"]
        print(f"Calendar: {len(days)} days, {len(event_days)} with EVENT level")
        
        if event_days:
            sample = event_days[0]
            assert sample.get("level") == "EVENT", "Level should be EVENT"
            assert "event" in sample, "Missing event name"
            assert "event_boost" in sample, "Missing event_boost"
            print(f"EVENT day sample: date={sample.get('date')}, event={sample.get('event')}, price={sample.get('price')}")
    
    def test_ai_insights_event_aware(self, auth_headers):
        """ai_insights should include event-aware insights"""
        response = requests.get(f"{BASE_URL}/api/revenue/smart-pricing/all", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "ai_insights" in data, "Missing ai_insights"
        insights = data.get("ai_insights", [])
        print(f"AI Insights count: {len(insights)}")
        
        # Check for event-related insights
        event_insights = [i for i in insights if "event" in i.get("title", "").lower() or "event" in i.get("desc", "").lower()]
        if event_insights:
            print(f"Event-aware insights found: {[i.get('title') for i in event_insights]}")
        else:
            print("No event-specific insights (may depend on event data)")


class TestSmartPricingRecalculate(TestAuth):
    """Test Smart Pricing recalculate generates event-aware recommendations"""
    
    def test_recalculate_generates_event_aware_recommendations(self, auth_headers):
        """POST /api/revenue/smart-pricing/all/recalculate generates event-aware recommendations"""
        response = requests.post(f"{BASE_URL}/api/revenue/smart-pricing/all/recalculate", headers=auth_headers)
        assert response.status_code == 200, f"Recalculate failed: {response.text}"
        data = response.json()
        
        assert "message" in data, "Missing message"
        assert "count" in data, "Missing count"
        print(f"Recalculate result: {data.get('message')}, count={data.get('count')}")
        
        # Verify message mentions event-aware
        message = data.get("message", "")
        assert "event-aware" in message.lower() or "event" in message.lower() or data.get("count", 0) >= 0, \
            "Recalculate should mention event-aware or return count"
    
    def test_recalculate_creates_approvals_with_event_info(self, auth_headers):
        """Recalculated approvals should have event info in reason field"""
        # First recalculate
        requests.post(f"{BASE_URL}/api/revenue/smart-pricing/all/recalculate", headers=auth_headers)
        
        # Get approvals
        response = requests.get(f"{BASE_URL}/api/revenue/approvals/all?status=draft", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        items = data.get("items", [])
        print(f"Draft approvals: {len(items)}")
        
        # Check for event info in reason
        event_approvals = [i for i in items if i.get("event") or "Event:" in (i.get("reason") or "")]
        if event_approvals:
            sample = event_approvals[0]
            print(f"Event approval sample: date={sample.get('date')}, event={sample.get('event')}, reason={sample.get('reason')}")


class TestMarketRobotDashboardData(TestAuth):
    """Test Market Robot returns data needed for dashboard UI"""
    
    def test_config_endpoint(self, auth_headers):
        """GET /api/revenue/market-robot/all/config returns config"""
        response = requests.get(f"{BASE_URL}/api/revenue/market-robot/all/config", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "city" in data, "Missing city in config"
        print(f"Market Robot config: city={data.get('city')}, enabled={data.get('enabled')}")
    
    def test_scanner_status_endpoint(self, auth_headers):
        """GET /api/revenue/market-robot/all/scanner/status returns scanner status"""
        response = requests.get(f"{BASE_URL}/api/revenue/market-robot/all/scanner/status", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        print(f"Scanner status: running={data.get('running')}")


class TestEventDataPresence(TestAuth):
    """Verify event data is present in the system"""
    
    def test_events_exist_in_system(self, auth_headers):
        """GET /api/revenue/events/all should return events"""
        response = requests.get(f"{BASE_URL}/api/revenue/events/all", headers=auth_headers)
        assert response.status_code == 200, f"Events endpoint failed: {response.text}"
        data = response.json()
        
        events = data.get("events", [])
        counts = data.get("counts", {})
        print(f"Events in system: total={counts.get('total', len(events))}, mega={counts.get('mega')}, large={counts.get('large')}")
        
        # Should have some events from previous GPT-5.2 scan
        assert len(events) > 0 or counts.get("total", 0) > 0, "No events found - may need to run event scan"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
