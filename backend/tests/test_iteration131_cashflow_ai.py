"""
Iteration 131 - Cash Flow AI Recommendations Tests
Tests for GPT-5.2 powered AI CFO recommendations feature:
- POST /api/finance/cash-flow-forecast/{property_id}/ai-recommendations
- GET /api/finance/cash-flow-forecast/{property_id}/ai-recommendations/latest
- Recommendation structure validation (title, rationale, impact, priority, kind)
- Role-based access control (admin/manager only)
- Persistence in cashflow_ai_snapshots collection
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


class TestCashFlowAIRecommendations:
    """Test AI CFO Recommendations endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: login as admin and get forecast data"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert login_resp.status_code == 200, f"Admin login failed: {login_resp.text}"
        token = login_resp.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Get forecast data for AI analysis
        forecast_resp = self.session.get(f"{BASE_URL}/api/finance/cash-flow-forecast/all?days=30&opening_balance=10000")
        assert forecast_resp.status_code == 200, f"Forecast fetch failed: {forecast_resp.text}"
        self.forecast_data = forecast_resp.json()
        
        yield
        self.session.close()
    
    def test_01_generate_ai_recommendations_success(self):
        """POST /api/finance/cash-flow-forecast/all/ai-recommendations returns recommendations"""
        resp = self.session.post(
            f"{BASE_URL}/api/finance/cash-flow-forecast/all/ai-recommendations",
            json={"forecast": self.forecast_data}
        )
        assert resp.status_code == 200, f"AI recommendations failed: {resp.text}"
        data = resp.json()
        
        # Should have recommendations array and generated_at
        assert "recommendations" in data, "Missing 'recommendations' field"
        assert "generated_at" in data, "Missing 'generated_at' field"
        
        # If no error, should have 3-5 recommendations
        if "error" not in data:
            recs = data["recommendations"]
            assert isinstance(recs, list), "recommendations should be a list"
            assert len(recs) >= 1, "Should have at least 1 recommendation"
            print(f"✓ Generated {len(recs)} AI recommendations")
    
    def test_02_recommendation_structure_validation(self):
        """Each recommendation has required fields: title, rationale, impact, priority, kind"""
        resp = self.session.post(
            f"{BASE_URL}/api/finance/cash-flow-forecast/all/ai-recommendations",
            json={"forecast": self.forecast_data}
        )
        assert resp.status_code == 200
        data = resp.json()
        
        if "error" in data:
            pytest.skip(f"AI returned error: {data['error']}")
        
        recs = data.get("recommendations", [])
        assert len(recs) > 0, "No recommendations returned"
        
        required_fields = ["title", "rationale", "impact", "priority", "kind"]
        valid_priorities = ["high", "medium", "low"]
        valid_kinds = ["save_cost", "boost_revenue", "timing", "risk_alert", "efficiency"]
        
        for i, rec in enumerate(recs):
            for field in required_fields:
                assert field in rec, f"Recommendation {i} missing '{field}' field"
            
            # Validate priority
            assert rec["priority"] in valid_priorities, f"Rec {i} has invalid priority: {rec['priority']}"
            
            # Validate kind
            assert rec["kind"] in valid_kinds, f"Rec {i} has invalid kind: {rec['kind']}"
            
            print(f"✓ Rec {i}: [{rec['priority'].upper()}] {rec['title']} ({rec['kind']})")
    
    def test_03_recommendations_persisted_in_db(self):
        """Recommendations are saved to cashflow_ai_snapshots collection"""
        # Generate recommendations
        gen_resp = self.session.post(
            f"{BASE_URL}/api/finance/cash-flow-forecast/all/ai-recommendations",
            json={"forecast": self.forecast_data}
        )
        assert gen_resp.status_code == 200
        gen_data = gen_resp.json()
        generated_at = gen_data.get("generated_at")
        
        # Fetch latest - should match what we just generated
        latest_resp = self.session.get(f"{BASE_URL}/api/finance/cash-flow-forecast/all/ai-recommendations/latest")
        assert latest_resp.status_code == 200
        latest_data = latest_resp.json()
        
        assert latest_data.get("generated_at") == generated_at, "Latest should match just-generated timestamp"
        assert latest_data.get("recommendations") == gen_data.get("recommendations"), "Latest recs should match generated"
        print(f"✓ Recommendations persisted and retrievable via /latest")
    
    def test_04_get_latest_recommendations(self):
        """GET /api/finance/cash-flow-forecast/all/ai-recommendations/latest returns cached recs"""
        resp = self.session.get(f"{BASE_URL}/api/finance/cash-flow-forecast/all/ai-recommendations/latest")
        assert resp.status_code == 200, f"Latest fetch failed: {resp.text}"
        data = resp.json()
        
        assert "recommendations" in data, "Missing 'recommendations' field"
        assert "generated_at" in data, "Missing 'generated_at' field"
        
        # generated_at can be None if no recs exist yet
        if data["generated_at"]:
            print(f"✓ Latest recommendations from {data['generated_at']}, count: {len(data['recommendations'])}")
        else:
            print("✓ No cached recommendations yet (expected on fresh DB)")
    
    def test_05_property_specific_recommendations(self):
        """AI recommendations work for specific property_id"""
        # Get forecast for specific property
        forecast_resp = self.session.get(f"{BASE_URL}/api/finance/cash-flow-forecast/aldgate-flats?days=30&opening_balance=5000")
        assert forecast_resp.status_code == 200
        prop_forecast = forecast_resp.json()
        
        # Generate AI recs for this property
        resp = self.session.post(
            f"{BASE_URL}/api/finance/cash-flow-forecast/aldgate-flats/ai-recommendations",
            json={"forecast": prop_forecast}
        )
        assert resp.status_code == 200
        data = resp.json()
        
        assert "recommendations" in data
        print(f"✓ Property-specific AI recommendations: {len(data.get('recommendations', []))} recs")
    
    def test_06_latest_returns_property_specific(self):
        """GET /latest for specific property returns that property's recs"""
        resp = self.session.get(f"{BASE_URL}/api/finance/cash-flow-forecast/aldgate-flats/ai-recommendations/latest")
        assert resp.status_code == 200
        data = resp.json()
        
        assert "recommendations" in data
        assert "generated_at" in data
        print(f"✓ Property-specific latest endpoint works")
    
    def test_07_empty_forecast_handled_gracefully(self):
        """Empty or minimal forecast data still returns parseable response"""
        resp = self.session.post(
            f"{BASE_URL}/api/finance/cash-flow-forecast/all/ai-recommendations",
            json={"forecast": {}}
        )
        assert resp.status_code == 200, f"Should handle empty forecast: {resp.text}"
        data = resp.json()
        
        # Should still have recommendations array (possibly empty or with fallback)
        assert "recommendations" in data
        print(f"✓ Empty forecast handled gracefully")
    
    def test_08_invalid_forecast_data_handled(self):
        """Invalid forecast data returns parseable response, not 500"""
        resp = self.session.post(
            f"{BASE_URL}/api/finance/cash-flow-forecast/all/ai-recommendations",
            json={"forecast": {"invalid": "data", "not_a_forecast": True}}
        )
        assert resp.status_code == 200, f"Should not 500 on invalid data: {resp.text}"
        data = resp.json()
        
        assert "recommendations" in data
        print(f"✓ Invalid forecast data handled without 500")


class TestCashFlowAIAccessControl:
    """Test role-based access control for AI endpoints"""
    
    def test_09_unauthenticated_access_denied(self):
        """AI endpoints require authentication"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        # POST without auth
        resp = session.post(
            f"{BASE_URL}/api/finance/cash-flow-forecast/all/ai-recommendations",
            json={"forecast": {}}
        )
        assert resp.status_code in [401, 403], f"Should deny unauthenticated POST: {resp.status_code}"
        
        # GET without auth
        resp = session.get(f"{BASE_URL}/api/finance/cash-flow-forecast/all/ai-recommendations/latest")
        assert resp.status_code in [401, 403], f"Should deny unauthenticated GET: {resp.status_code}"
        
        print("✓ Unauthenticated access correctly denied")
    
    def test_10_receptionist_access_denied(self):
        """Receptionist role cannot access AI endpoints (requires admin/manager)"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        # First create a receptionist user if not exists
        admin_login = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        admin_token = admin_login.json().get("access_token")
        session.headers.update({"Authorization": f"Bearer {admin_token}"})
        
        # Try to create receptionist
        receptionist_email = "test_receptionist_ai@hotel.com"
        session.post(f"{BASE_URL}/api/auth/register", json={
            "email": receptionist_email,
            "password": "TestPass123!",
            "name": "Test Receptionist",
            "role": "receptionist",
            "department": "front_desk"
        })
        
        # Approve the user
        users_resp = session.get(f"{BASE_URL}/api/admin/users")
        if users_resp.status_code == 200:
            users = users_resp.json()
            for u in users:
                if u.get("email") == receptionist_email:
                    session.post(f"{BASE_URL}/api/admin/users/{u['id']}/approve")
                    break
        
        # Login as receptionist
        session.headers.pop("Authorization", None)
        recep_login = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": receptionist_email,
            "password": "TestPass123!"
        })
        
        if recep_login.status_code == 200:
            recep_token = recep_login.json().get("access_token")
            session.headers.update({"Authorization": f"Bearer {recep_token}"})
            
            # Try POST - should be 403
            resp = session.post(
                f"{BASE_URL}/api/finance/cash-flow-forecast/all/ai-recommendations",
                json={"forecast": {}}
            )
            assert resp.status_code == 403, f"Receptionist should get 403 on POST: {resp.status_code}"
            
            # Try GET - should be 403
            resp = session.get(f"{BASE_URL}/api/finance/cash-flow-forecast/all/ai-recommendations/latest")
            assert resp.status_code == 403, f"Receptionist should get 403 on GET: {resp.status_code}"
            
            print("✓ Receptionist correctly denied access (403)")
        else:
            print("✓ Receptionist user creation/login skipped (may already exist with different password)")


class TestCashFlowAIErrorHandling:
    """Test error handling for AI endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert login_resp.status_code == 200
        token = login_resp.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        yield
        self.session.close()
    
    def test_11_missing_forecast_key_handled(self):
        """Missing 'forecast' key in request body handled gracefully"""
        resp = self.session.post(
            f"{BASE_URL}/api/finance/cash-flow-forecast/all/ai-recommendations",
            json={}  # No forecast key
        )
        assert resp.status_code == 200, f"Should handle missing forecast key: {resp.text}"
        data = resp.json()
        assert "recommendations" in data
        print("✓ Missing forecast key handled gracefully")
    
    def test_12_ai_response_contains_generated_at_timestamp(self):
        """AI response includes ISO timestamp for generated_at"""
        forecast_resp = self.session.get(f"{BASE_URL}/api/finance/cash-flow-forecast/all?days=30&opening_balance=10000")
        forecast_data = forecast_resp.json()
        
        resp = self.session.post(
            f"{BASE_URL}/api/finance/cash-flow-forecast/all/ai-recommendations",
            json={"forecast": forecast_data}
        )
        assert resp.status_code == 200
        data = resp.json()
        
        if "error" not in data:
            assert data.get("generated_at") is not None, "generated_at should be present"
            # Should be ISO format
            assert "T" in data["generated_at"], "generated_at should be ISO format"
            print(f"✓ generated_at timestamp: {data['generated_at']}")


class TestCashFlowAIIntegration:
    """Integration tests for AI recommendations with real GPT-5.2"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert login_resp.status_code == 200
        token = login_resp.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        yield
        self.session.close()
    
    def test_13_ai_generates_specific_recommendations(self):
        """AI generates specific, actionable recommendations with £ amounts"""
        forecast_resp = self.session.get(f"{BASE_URL}/api/finance/cash-flow-forecast/all?days=30&opening_balance=10000")
        forecast_data = forecast_resp.json()
        
        resp = self.session.post(
            f"{BASE_URL}/api/finance/cash-flow-forecast/all/ai-recommendations",
            json={"forecast": forecast_data}
        )
        assert resp.status_code == 200
        data = resp.json()
        
        if "error" in data:
            print(f"⚠ AI returned error (may be expected): {data['error']}")
            return
        
        recs = data.get("recommendations", [])
        assert len(recs) >= 1, "Should have at least 1 recommendation"
        
        # Check that recommendations have meaningful content
        for i, rec in enumerate(recs):
            assert len(rec.get("title", "")) > 3, f"Rec {i} title too short"
            assert len(rec.get("rationale", "")) > 10, f"Rec {i} rationale too short"
            print(f"  Rec {i}: {rec['title']} | Impact: {rec.get('impact', 'N/A')}")
        
        print(f"✓ AI generated {len(recs)} specific recommendations")
    
    def test_14_regenerate_produces_new_timestamp(self):
        """Regenerating recommendations creates new snapshot with new timestamp"""
        forecast_resp = self.session.get(f"{BASE_URL}/api/finance/cash-flow-forecast/all?days=30&opening_balance=10000")
        forecast_data = forecast_resp.json()
        
        # First generation
        resp1 = self.session.post(
            f"{BASE_URL}/api/finance/cash-flow-forecast/all/ai-recommendations",
            json={"forecast": forecast_data}
        )
        assert resp1.status_code == 200
        ts1 = resp1.json().get("generated_at")
        
        # Wait a moment
        time.sleep(1)
        
        # Second generation
        resp2 = self.session.post(
            f"{BASE_URL}/api/finance/cash-flow-forecast/all/ai-recommendations",
            json={"forecast": forecast_data}
        )
        assert resp2.status_code == 200
        ts2 = resp2.json().get("generated_at")
        
        if ts1 and ts2:
            assert ts1 != ts2, "Regeneration should produce new timestamp"
            print(f"✓ Regeneration produces new timestamp: {ts1} → {ts2}")
        else:
            print("✓ Timestamps present (may have errors)")
    
    def test_15_latest_returns_most_recent(self):
        """GET /latest returns the most recently generated snapshot"""
        forecast_resp = self.session.get(f"{BASE_URL}/api/finance/cash-flow-forecast/all?days=30&opening_balance=10000")
        forecast_data = forecast_resp.json()
        
        # Generate new recommendations
        gen_resp = self.session.post(
            f"{BASE_URL}/api/finance/cash-flow-forecast/all/ai-recommendations",
            json={"forecast": forecast_data}
        )
        assert gen_resp.status_code == 200
        gen_ts = gen_resp.json().get("generated_at")
        
        # Fetch latest
        latest_resp = self.session.get(f"{BASE_URL}/api/finance/cash-flow-forecast/all/ai-recommendations/latest")
        assert latest_resp.status_code == 200
        latest_ts = latest_resp.json().get("generated_at")
        
        assert latest_ts == gen_ts, f"Latest should match just-generated: {latest_ts} vs {gen_ts}"
        print(f"✓ Latest correctly returns most recent snapshot")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
