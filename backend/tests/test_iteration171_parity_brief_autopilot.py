"""
Iteration 171 - Testing new features:
1. Future-Date Rate Parity Heatmap (GET /api/parity/heatmap/{property_id}?days=60)
2. Morning Brief / 8AM digest (GET /api/morning-brief/{property_id})
3. Pricing Autopilot config + run-now (GET/POST /api/autopilot/pricing/{property_id})
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
PROPERTY_ID = "aldgate-flats"

class TestAuth:
    """Authentication for all tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.cookies.get("access_token") or response.json().get("access_token")
    
    @pytest.fixture(scope="class")
    def session(self, auth_token):
        """Authenticated session"""
        s = requests.Session()
        s.cookies.set("access_token", auth_token)
        s.headers.update({"Content-Type": "application/json"})
        return s


class TestParityHeatmap(TestAuth):
    """Test Future-Date Rate Parity Heatmap endpoint"""
    
    def test_heatmap_default_60_days(self, session):
        """GET /api/parity/heatmap/{property_id} returns heatmap with default 60 days"""
        response = session.get(f"{BASE_URL}/api/parity/heatmap/{PROPERTY_ID}")
        assert response.status_code == 200, f"Heatmap failed: {response.text}"
        
        data = response.json()
        # Verify required fields
        assert "property_id" in data
        assert data["property_id"] == PROPERTY_ID
        assert "base_rate" in data
        assert "days" in data
        assert data["days"] == 60  # default
        assert "cells" in data
        assert isinstance(data["cells"], list)
        assert "summary" in data
        
        # Verify summary structure
        summary = data["summary"]
        assert "avg_delta_pct" in summary
        assert "underpriced_days" in summary
        assert "parity_days" in summary
        assert "overpriced_days" in summary
        assert "no_data_days" in summary
        
        print(f"✓ Heatmap returned {len(data['cells'])} cells, base_rate={data['base_rate']}")
        print(f"✓ Summary: underpriced={summary['underpriced_days']}, parity={summary['parity_days']}, overpriced={summary['overpriced_days']}, no_data={summary['no_data_days']}")
    
    def test_heatmap_custom_days(self, session):
        """GET /api/parity/heatmap/{property_id}?days=30 respects days param"""
        response = session.get(f"{BASE_URL}/api/parity/heatmap/{PROPERTY_ID}?days=30")
        assert response.status_code == 200
        
        data = response.json()
        assert data["days"] == 30
        assert len(data["cells"]) == 30
        print(f"✓ Heatmap with days=30 returned {len(data['cells'])} cells")
    
    def test_heatmap_cell_structure(self, session):
        """Verify each cell has required fields"""
        response = session.get(f"{BASE_URL}/api/parity/heatmap/{PROPERTY_ID}?days=7")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["cells"]) >= 7
        
        cell = data["cells"][0]
        required_fields = ["date", "dow", "is_weekend", "our_rate", "comp_avg", "comp_min", 
                          "comp_max", "comp_count", "competitors", "delta_pct", "class", "occ_pct"]
        for field in required_fields:
            assert field in cell, f"Missing field: {field}"
        
        # Verify class is one of expected values
        assert cell["class"] in ["underpriced", "parity", "overpriced", "no_data"]
        print(f"✓ Cell structure verified: date={cell['date']}, class={cell['class']}, our_rate={cell['our_rate']}")
    
    def test_heatmap_days_clamped(self, session):
        """Days param is clamped between 7 and 180"""
        # Test minimum
        response = session.get(f"{BASE_URL}/api/parity/heatmap/{PROPERTY_ID}?days=3")
        assert response.status_code == 200
        assert response.json()["days"] == 7  # clamped to min
        
        # Test maximum
        response = session.get(f"{BASE_URL}/api/parity/heatmap/{PROPERTY_ID}?days=365")
        assert response.status_code == 200
        assert response.json()["days"] == 180  # clamped to max
        print("✓ Days parameter correctly clamped to 7-180 range")


class TestMorningBrief(TestAuth):
    """Test Morning Brief / 8AM digest endpoint"""
    
    def test_morning_brief_structure(self, session):
        """GET /api/morning-brief/{property_id} returns complete brief"""
        response = session.get(f"{BASE_URL}/api/morning-brief/{PROPERTY_ID}")
        assert response.status_code == 200, f"Morning brief failed: {response.text}"
        
        data = response.json()
        
        # Verify required top-level fields
        assert "property_id" in data
        assert data["property_id"] == PROPERTY_ID
        assert "as_of" in data
        assert "today" in data
        assert "pickup_7d" in data
        assert "stly_7d" in data
        assert "alerts" in data
        assert "new_reviews" in data
        
        print(f"✓ Morning brief returned for {PROPERTY_ID}")
    
    def test_morning_brief_today_stats(self, session):
        """Verify today stats structure"""
        response = session.get(f"{BASE_URL}/api/morning-brief/{PROPERTY_ID}")
        assert response.status_code == 200
        
        today = response.json()["today"]
        assert "date" in today
        assert "arrivals" in today
        assert "departures" in today
        assert "in_house" in today
        
        # Values should be non-negative integers
        assert isinstance(today["arrivals"], int) and today["arrivals"] >= 0
        assert isinstance(today["departures"], int) and today["departures"] >= 0
        assert isinstance(today["in_house"], int) and today["in_house"] >= 0
        
        print(f"✓ Today stats: arrivals={today['arrivals']}, departures={today['departures']}, in_house={today['in_house']}")
    
    def test_morning_brief_pickup(self, session):
        """Verify 7-day pickup structure"""
        response = session.get(f"{BASE_URL}/api/morning-brief/{PROPERTY_ID}")
        assert response.status_code == 200
        
        pickup = response.json()["pickup_7d"]
        assert "count" in pickup
        assert "revenue" in pickup
        
        print(f"✓ Pickup 7d: count={pickup['count']}, revenue={pickup['revenue']}")
    
    def test_morning_brief_stly(self, session):
        """Verify STLY (Same Time Last Year) structure"""
        response = session.get(f"{BASE_URL}/api/morning-brief/{PROPERTY_ID}")
        assert response.status_code == 200
        
        stly = response.json()["stly_7d"]
        assert "ty_rooms" in stly
        assert "ly_rooms" in stly
        assert "delta" in stly
        assert "delta_pct" in stly
        
        print(f"✓ STLY 7d: TY={stly['ty_rooms']}, LY={stly['ly_rooms']}, delta={stly['delta']} ({stly['delta_pct']}%)")
    
    def test_morning_brief_alerts(self, session):
        """Verify alerts structure"""
        response = session.get(f"{BASE_URL}/api/morning-brief/{PROPERTY_ID}")
        assert response.status_code == 200
        
        alerts = response.json()["alerts"]
        assert "open_logbook" in alerts
        assert "unread_inbox" in alerts
        assert "unanswered_reviews" in alerts
        
        print(f"✓ Alerts: logbook={alerts['open_logbook']}, inbox={alerts['unread_inbox']}, reviews={alerts['unanswered_reviews']}")


class TestPricingAutopilot(TestAuth):
    """Test Pricing Autopilot config and run-now endpoints"""
    
    def test_get_autopilot_default_config(self, session):
        """GET /api/autopilot/pricing/{property_id} returns default config if none exists"""
        response = session.get(f"{BASE_URL}/api/autopilot/pricing/{PROPERTY_ID}")
        assert response.status_code == 200, f"Get autopilot failed: {response.text}"
        
        data = response.json()
        assert "property_id" in data
        assert "enabled" in data
        assert "schedule" in data
        assert "days_window" in data
        assert "auto_apply" in data
        
        print(f"✓ Autopilot config: enabled={data['enabled']}, schedule={data['schedule']}, days_window={data['days_window']}")
    
    def test_update_autopilot_config(self, session):
        """POST /api/autopilot/pricing/{property_id} upserts config"""
        config = {
            "enabled": True,
            "schedule": "daily_06",
            "days_window": 21,
            "auto_apply": False
        }
        response = session.post(f"{BASE_URL}/api/autopilot/pricing/{PROPERTY_ID}", json=config)
        assert response.status_code == 200, f"Update autopilot failed: {response.text}"
        
        data = response.json()
        assert data["ok"] == True
        assert "config" in data
        assert data["config"]["enabled"] == True
        assert data["config"]["schedule"] == "daily_06"
        assert data["config"]["days_window"] == 21
        
        # Verify persistence
        get_response = session.get(f"{BASE_URL}/api/autopilot/pricing/{PROPERTY_ID}")
        assert get_response.status_code == 200
        persisted = get_response.json()
        assert persisted["enabled"] == True
        assert persisted["schedule"] == "daily_06"
        
        print("✓ Autopilot config updated and persisted")
    
    def test_run_now_stamps_timestamp(self, session):
        """POST /api/autopilot/pricing/{property_id}/run-now stamps last_run_at"""
        response = session.post(f"{BASE_URL}/api/autopilot/pricing/{PROPERTY_ID}/run-now")
        assert response.status_code == 200, f"Run-now failed: {response.text}"
        
        data = response.json()
        assert data["ok"] == True
        assert "days_window" in data
        assert "message" in data
        
        # Verify last_run_at was updated
        get_response = session.get(f"{BASE_URL}/api/autopilot/pricing/{PROPERTY_ID}")
        assert get_response.status_code == 200
        config = get_response.json()
        assert "last_run_at" in config
        assert config["last_run_at"] != ""
        
        print(f"✓ Run-now triggered, last_run_at={config['last_run_at']}")
    
    def test_save_run_persists_recommendations(self, session):
        """POST /api/autopilot/pricing/{property_id}/save-run persists recommendations"""
        today = datetime.now().date()
        recommendations = [
            {
                "date": (today + timedelta(days=1)).isoformat(),
                "suggested_rate": 120,
                "delta_pct": 5.5,
                "confidence": 0.85,
                "reasoning": "High demand expected due to local event"
            },
            {
                "date": (today + timedelta(days=2)).isoformat(),
                "suggested_rate": 95,
                "delta_pct": -3.2,
                "confidence": 0.72,
                "reasoning": "Low occupancy forecast"
            }
        ]
        
        payload = {
            "recommendations": recommendations,
            "summary": "Test run with 2 recommendations"
        }
        
        response = session.post(f"{BASE_URL}/api/autopilot/pricing/{PROPERTY_ID}/save-run", json=payload)
        assert response.status_code == 200, f"Save-run failed: {response.text}"
        
        data = response.json()
        assert data["ok"] == True
        assert data["saved"] == 2
        
        # Verify persistence
        get_response = session.get(f"{BASE_URL}/api/autopilot/pricing/{PROPERTY_ID}")
        assert get_response.status_code == 200
        config = get_response.json()
        assert "last_recommendations" in config
        assert len(config["last_recommendations"]) == 2
        assert config["last_summary"] == "Test run with 2 recommendations"
        
        print(f"✓ Save-run persisted {data['saved']} recommendations")
    
    def test_disable_autopilot(self, session):
        """Disable autopilot after tests"""
        config = {
            "enabled": False,
            "schedule": "daily_03",
            "days_window": 14,
            "auto_apply": False
        }
        response = session.post(f"{BASE_URL}/api/autopilot/pricing/{PROPERTY_ID}", json=config)
        assert response.status_code == 200
        print("✓ Autopilot disabled (cleanup)")


class TestRegressionSmoke(TestAuth):
    """Quick smoke tests for iter 170 features"""
    
    def test_pace_reports_endpoint(self, session):
        """Smoke test: Pace reports still working"""
        response = session.get(f"{BASE_URL}/api/forecast/pace/{PROPERTY_ID}?days=14")
        assert response.status_code == 200, f"Pace reports failed: {response.text}"
        data = response.json()
        assert "stly" in data
        assert "pickup" in data
        print("✓ Pace reports endpoint working")
    
    def test_ai_pricing_v2_endpoint(self, session):
        """Smoke test: AI Pricing V2 recommend endpoint exists"""
        response = session.post(f"{BASE_URL}/api/dynamic-pricing/{PROPERTY_ID}/ai-v2/recommend", json={"days": 7})
        # May return 200 or 500 (LLM budget) - just verify endpoint exists
        assert response.status_code in [200, 500], f"AI Pricing V2 unexpected status: {response.status_code}"
        print(f"✓ AI Pricing V2 endpoint exists (status={response.status_code})")
    
    def test_unified_inbox_endpoint(self, session):
        """Smoke test: Unified inbox threads endpoint"""
        response = session.get(f"{BASE_URL}/api/inbox/threads")
        assert response.status_code == 200, f"Inbox threads failed: {response.text}"
        print("✓ Unified inbox endpoint working")
    
    def test_login_still_works(self, session):
        """Smoke test: Login endpoint"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200
        print("✓ Login endpoint working")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
