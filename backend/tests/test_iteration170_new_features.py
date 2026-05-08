"""
Iteration 170 - Testing new features:
1. Pace Reports (STLY + Pickup + Source contribution) - GET /api/forecast/pace/{property_id}
2. AI Dynamic Pricing v2 (GPT-5.2) - POST /api/dynamic-pricing/{property_id}/ai-v2/recommend
3. AI Dynamic Pricing v2 Apply - POST /api/dynamic-pricing/{property_id}/ai-v2/apply
4. Inbox AI Suggest Reply - POST /api/inbox/threads/{guest_key}/ai-suggest
5. Regression tests for existing endpoints
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
PROPERTY_ID = "aldgate-flats"

class TestAuth:
    """Authentication tests - regression"""
    
    @pytest.fixture(scope="class")
    def session(self):
        return requests.Session()
    
    def test_admin_login(self, session):
        """Test admin login still works"""
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        # Login returns user data directly (not wrapped in "user" key)
        assert "email" in data
        assert data["email"] == "admin@hotelbox.com"
        print(f"✓ Admin login successful: {data.get('name', data['email'])}")


class TestPaceReports:
    """Pace Reports - STLY + Pickup + Source contribution"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200, "Auth failed"
        return session
    
    def test_pace_report_default_days(self, auth_session):
        """GET /api/forecast/pace/{property_id} - default 30 days"""
        response = auth_session.get(f"{BASE_URL}/api/forecast/pace/{PROPERTY_ID}")
        assert response.status_code == 200, f"Pace report failed: {response.text}"
        data = response.json()
        
        # Verify structure
        assert "stly" in data, "Missing stly array"
        assert "pickup" in data, "Missing pickup object"
        assert "source_contribution" in data, "Missing source_contribution array"
        assert "totals" in data, "Missing totals object"
        
        # Verify stly structure
        assert isinstance(data["stly"], list), "stly should be a list"
        if len(data["stly"]) > 0:
            stly_item = data["stly"][0]
            assert "date" in stly_item
            assert "ly_date" in stly_item
            assert "ty_rooms" in stly_item
            assert "ly_rooms" in stly_item
            assert "delta" in stly_item
            assert "delta_pct" in stly_item
        
        # Verify pickup structure
        assert "last_7d" in data["pickup"], "Missing last_7d in pickup"
        assert "last_14d" in data["pickup"], "Missing last_14d in pickup"
        assert "last_30d" in data["pickup"], "Missing last_30d in pickup"
        
        for window in ["last_7d", "last_14d", "last_30d"]:
            pickup_data = data["pickup"][window]
            assert "total_bookings" in pickup_data
            assert "total_revenue" in pickup_data
            assert "by_source" in pickup_data
        
        # Verify totals structure
        assert "ty_total_rooms" in data["totals"]
        assert "ly_total_rooms" in data["totals"]
        assert "forecast_revenue" in data["totals"]
        
        print(f"✓ Pace report returned {len(data['stly'])} STLY days")
        print(f"  Totals: TY={data['totals']['ty_total_rooms']}, LY={data['totals']['ly_total_rooms']}")
    
    def test_pace_report_14_days(self, auth_session):
        """GET /api/forecast/pace/{property_id}?days=14"""
        response = auth_session.get(f"{BASE_URL}/api/forecast/pace/{PROPERTY_ID}?days=14")
        assert response.status_code == 200
        data = response.json()
        
        assert data["window_days"] == 14
        assert len(data["stly"]) == 14, f"Expected 14 STLY days, got {len(data['stly'])}"
        print(f"✓ Pace report with days=14 returned {len(data['stly'])} days")
    
    def test_pace_report_60_days(self, auth_session):
        """GET /api/forecast/pace/{property_id}?days=60"""
        response = auth_session.get(f"{BASE_URL}/api/forecast/pace/{PROPERTY_ID}?days=60")
        assert response.status_code == 200
        data = response.json()
        
        assert data["window_days"] == 60
        assert len(data["stly"]) == 60
        print(f"✓ Pace report with days=60 returned {len(data['stly'])} days")
    
    def test_pace_report_90_days(self, auth_session):
        """GET /api/forecast/pace/{property_id}?days=90"""
        response = auth_session.get(f"{BASE_URL}/api/forecast/pace/{PROPERTY_ID}?days=90")
        assert response.status_code == 200
        data = response.json()
        
        assert data["window_days"] == 90
        assert len(data["stly"]) == 90
        print(f"✓ Pace report with days=90 returned {len(data['stly'])} days")
    
    def test_pace_report_180_days(self, auth_session):
        """GET /api/forecast/pace/{property_id}?days=180"""
        response = auth_session.get(f"{BASE_URL}/api/forecast/pace/{PROPERTY_ID}?days=180")
        assert response.status_code == 200
        data = response.json()
        
        assert data["window_days"] == 180
        assert len(data["stly"]) == 180
        print(f"✓ Pace report with days=180 returned {len(data['stly'])} days")
    
    def test_pace_report_min_days_clamped(self, auth_session):
        """GET /api/forecast/pace/{property_id}?days=3 - should clamp to 7"""
        response = auth_session.get(f"{BASE_URL}/api/forecast/pace/{PROPERTY_ID}?days=3")
        assert response.status_code == 200
        data = response.json()
        
        # Should be clamped to minimum 7 days
        assert data["window_days"] >= 7, f"Expected min 7 days, got {data['window_days']}"
        print(f"✓ Pace report with days=3 clamped to {data['window_days']} days")


class TestAIPricingV2:
    """AI Dynamic Pricing v2 - GPT-5.2 recommendations"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200, "Auth failed"
        return session
    
    def test_ai_v2_recommend_default(self, auth_session):
        """POST /api/dynamic-pricing/{property_id}/ai-v2/recommend - default 14 days"""
        response = auth_session.post(
            f"{BASE_URL}/api/dynamic-pricing/{PROPERTY_ID}/ai-v2/recommend",
            json={}
        )
        assert response.status_code == 200, f"AI v2 recommend failed: {response.text}"
        data = response.json()
        
        # Verify structure
        assert "recommendations" in data, "Missing recommendations array"
        assert "summary" in data, "Missing summary"
        assert "room_type" in data, "Missing room_type"
        
        # Check if fallback or real LLM response
        if data.get("fallback"):
            print("⚠ AI v2 returned fallback (heuristic) response - LLM key may be missing")
        else:
            print("✓ AI v2 returned real GPT-5.2 response")
        
        # Verify recommendations structure
        recs = data["recommendations"]
        assert isinstance(recs, list), "recommendations should be a list"
        
        if len(recs) > 0:
            rec = recs[0]
            assert "date" in rec, "Missing date in recommendation"
            assert "dow" in rec, "Missing dow in recommendation"
            assert "current_rate" in rec or "suggested_rate" in rec, "Missing rate fields"
            assert "suggested_rate" in rec, "Missing suggested_rate"
            assert "delta_pct" in rec, "Missing delta_pct"
            assert "confidence" in rec, "Missing confidence"
            assert "reasoning" in rec, "Missing reasoning"
            assert "signals" in rec, "Missing signals"
        
        print(f"✓ AI v2 recommend returned {len(recs)} recommendations")
        print(f"  Summary: {data.get('summary', 'N/A')[:100]}...")
    
    def test_ai_v2_recommend_with_days(self, auth_session):
        """POST /api/dynamic-pricing/{property_id}/ai-v2/recommend with days=7"""
        response = auth_session.post(
            f"{BASE_URL}/api/dynamic-pricing/{PROPERTY_ID}/ai-v2/recommend",
            json={"days": 7}
        )
        assert response.status_code == 200
        data = response.json()
        
        recs = data.get("recommendations", [])
        # Should have 7 recommendations (one per day)
        assert len(recs) == 7, f"Expected 7 recommendations, got {len(recs)}"
        print(f"✓ AI v2 recommend with days=7 returned {len(recs)} recommendations")
    
    def test_ai_v2_recommend_with_room_type(self, auth_session):
        """POST /api/dynamic-pricing/{property_id}/ai-v2/recommend with room_type_id"""
        # First get room types
        rt_response = auth_session.get(f"{BASE_URL}/api/room-types?property_id={PROPERTY_ID}")
        if rt_response.status_code == 200:
            room_types = rt_response.json()
            if room_types:
                room_type_id = room_types[0].get("id")
                
                response = auth_session.post(
                    f"{BASE_URL}/api/dynamic-pricing/{PROPERTY_ID}/ai-v2/recommend",
                    json={"days": 7, "room_type_id": room_type_id}
                )
                assert response.status_code == 200
                data = response.json()
                
                assert data.get("room_type_id") == room_type_id
                print(f"✓ AI v2 recommend with room_type_id={room_type_id}")
            else:
                print("⚠ No room types found, skipping room_type_id test")
        else:
            print("⚠ Could not fetch room types, skipping room_type_id test")
    
    def test_ai_v2_apply(self, auth_session):
        """POST /api/dynamic-pricing/{property_id}/ai-v2/apply"""
        # First get recommendations
        rec_response = auth_session.post(
            f"{BASE_URL}/api/dynamic-pricing/{PROPERTY_ID}/ai-v2/recommend",
            json={"days": 7}
        )
        assert rec_response.status_code == 200
        rec_data = rec_response.json()
        
        recs = rec_data.get("recommendations", [])
        room_type_id = rec_data.get("room_type_id")
        
        if not recs or not room_type_id:
            pytest.skip("No recommendations to apply")
        
        # Apply first 3 recommendations
        apply_recs = recs[:3]
        response = auth_session.post(
            f"{BASE_URL}/api/dynamic-pricing/{PROPERTY_ID}/ai-v2/apply",
            json={
                "room_type_id": room_type_id,
                "recommendations": apply_recs
            }
        )
        assert response.status_code == 200, f"AI v2 apply failed: {response.text}"
        data = response.json()
        
        assert "applied" in data, "Missing applied count"
        assert data["applied"] == len(apply_recs), f"Expected {len(apply_recs)} applied, got {data['applied']}"
        print(f"✓ AI v2 apply successfully applied {data['applied']} rate(s)")
    
    def test_ai_v2_apply_validation(self, auth_session):
        """POST /api/dynamic-pricing/{property_id}/ai-v2/apply - validation errors"""
        # Missing room_type_id
        response = auth_session.post(
            f"{BASE_URL}/api/dynamic-pricing/{PROPERTY_ID}/ai-v2/apply",
            json={"recommendations": []}
        )
        assert response.status_code == 400, "Should fail without room_type_id"
        
        # Missing recommendations
        response = auth_session.post(
            f"{BASE_URL}/api/dynamic-pricing/{PROPERTY_ID}/ai-v2/apply",
            json={"room_type_id": "test"}
        )
        assert response.status_code == 400, "Should fail without recommendations"
        print("✓ AI v2 apply validation working correctly")


class TestInboxAISuggest:
    """Inbox AI Suggest Reply - GPT-5.2 tone variants"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200, "Auth failed"
        return session
    
    def test_inbox_threads_list(self, auth_session):
        """GET /api/inbox/threads - regression test"""
        response = auth_session.get(f"{BASE_URL}/api/inbox/threads")
        assert response.status_code == 200, f"Inbox threads failed: {response.text}"
        data = response.json()
        
        assert isinstance(data, list), "threads should be a list"
        print(f"✓ Inbox threads returned {len(data)} threads")
        return data
    
    def test_create_test_thread_via_webhook(self, auth_session):
        """POST /api/inbox/webhook/whatsapp - create test thread"""
        test_guest_key = "+447700900123"
        response = auth_session.post(
            f"{BASE_URL}/api/inbox/webhook/whatsapp",
            json={
                "guest_key": test_guest_key,
                "guest_name": "Test Guest",
                "body": "Hi, I have a question about my booking. Can I get a late checkout?",
                "from": test_guest_key
            }
        )
        assert response.status_code == 200, f"Webhook failed: {response.text}"
        data = response.json()
        
        assert data.get("ok") == True
        assert "id" in data
        print(f"✓ Created test thread via webhook: {data['id']}")
        return test_guest_key
    
    def test_ai_suggest_reply(self, auth_session):
        """POST /api/inbox/threads/{guest_key}/ai-suggest"""
        test_guest_key = "+447700900123"
        
        # First ensure thread exists
        auth_session.post(
            f"{BASE_URL}/api/inbox/webhook/whatsapp",
            json={
                "guest_key": test_guest_key,
                "guest_name": "Test Guest",
                "body": "Hi, I have a question about my booking. Can I get a late checkout?",
                "from": test_guest_key
            }
        )
        
        # Now test AI suggest
        response = auth_session.post(
            f"{BASE_URL}/api/inbox/threads/{test_guest_key}/ai-suggest",
            json={"channel": "whatsapp", "hotel_name": "Aldgate Flats"}
        )
        assert response.status_code == 200, f"AI suggest failed: {response.text}"
        data = response.json()
        
        # Verify structure
        assert "suggestions" in data, "Missing suggestions array"
        suggestions = data["suggestions"]
        
        assert isinstance(suggestions, list), "suggestions should be a list"
        assert len(suggestions) >= 1, "Should have at least 1 suggestion"
        
        # Check if fallback or real LLM response
        if data.get("fallback"):
            print("⚠ AI suggest returned fallback response - LLM key may be missing")
        else:
            print("✓ AI suggest returned real GPT-5.2 response")
        
        # Verify suggestion structure
        for sugg in suggestions:
            assert "tone" in sugg, "Missing tone in suggestion"
            assert "body" in sugg, "Missing body in suggestion"
            assert "channel" in sugg, "Missing channel in suggestion"
        
        # Check for expected tones
        tones = [s.get("tone") for s in suggestions]
        print(f"✓ AI suggest returned {len(suggestions)} suggestions with tones: {tones}")
        
        # If not fallback, should have warm/brief/apologetic
        if not data.get("fallback"):
            expected_tones = {"warm", "brief", "apologetic"}
            actual_tones = set(tones)
            assert expected_tones.issubset(actual_tones) or len(actual_tones) >= 3, \
                f"Expected tones {expected_tones}, got {actual_tones}"
    
    def test_ai_suggest_nonexistent_thread(self, auth_session):
        """POST /api/inbox/threads/{guest_key}/ai-suggest - nonexistent thread"""
        response = auth_session.post(
            f"{BASE_URL}/api/inbox/threads/nonexistent-guest-key-12345/ai-suggest",
            json={}
        )
        assert response.status_code == 404, "Should return 404 for nonexistent thread"
        print("✓ AI suggest correctly returns 404 for nonexistent thread")


class TestRegressionEndpoints:
    """Regression tests for existing endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200, "Auth failed"
        return session
    
    def test_properties_list(self, auth_session):
        """GET /api/properties - regression"""
        response = auth_session.get(f"{BASE_URL}/api/properties")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Properties list returned {len(data)} properties")
    
    def test_room_types_list(self, auth_session):
        """GET /api/room-types - regression"""
        response = auth_session.get(f"{BASE_URL}/api/room-types?property_id={PROPERTY_ID}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Room types list returned {len(data)} room types")
    
    def test_occupancy_forecast(self, auth_session):
        """GET /api/forecast/occupancy/{property_id} - regression"""
        response = auth_session.get(f"{BASE_URL}/api/forecast/occupancy/{PROPERTY_ID}?days=30")
        assert response.status_code == 200
        data = response.json()
        assert "forecast" in data
        assert "summary" in data
        print(f"✓ Occupancy forecast returned {len(data.get('forecast', []))} days")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
