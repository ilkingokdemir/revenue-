"""
Batch 14 - AI Predictions: Cancellation Risk Scoring + Upsell Propensity Scoring
Tests for:
- GET /api/ai-predictions/cancel-risk/{property_id} - List cancel risk scores
- GET /api/ai-predictions/cancel-risk/booking/{booking_id} - Single booking risk
- POST /api/ai-predictions/cancel-risk/{booking_id}/save-offer - Queue save-offer
- GET /api/ai-predictions/upsell/{property_id} - List upsell propensity scores
- POST /api/ai-predictions/upsell/{booking_id}/send-offer - Queue upsell offer
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

@pytest.fixture(scope="module")
def auth_token():
    """Get admin auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    if response.status_code == 200:
        return response.cookies.get("access_token") or response.json().get("access_token")
    pytest.skip("Authentication failed")

@pytest.fixture(scope="module")
def auth_session(auth_token):
    """Session with auth cookies"""
    session = requests.Session()
    session.cookies.set("access_token", auth_token)
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestCancelRiskList:
    """Test GET /api/ai-predictions/cancel-risk/{property_id}"""
    
    def test_cancel_risk_list_default_property(self, auth_session):
        """Test cancel risk list for default property with default params"""
        response = auth_session.get(f"{BASE_URL}/api/ai-predictions/cancel-risk/default")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify response structure
        assert "rows" in data, "Response should have 'rows'"
        assert "by_band" in data, "Response should have 'by_band'"
        assert "at_risk_revenue" in data, "Response should have 'at_risk_revenue'"
        assert "count" in data, "Response should have 'count'"
        
        # Verify by_band structure
        by_band = data["by_band"]
        assert "high" in by_band, "by_band should have 'high'"
        assert "medium" in by_band, "by_band should have 'medium'"
        assert "low" in by_band, "by_band should have 'low'"
        
        print(f"Cancel risk list: {data['count']} rows, by_band={by_band}, at_risk_revenue={data['at_risk_revenue']}")
    
    def test_cancel_risk_list_with_filters(self, auth_session):
        """Test cancel risk list with days_ahead=60 and min_score=30"""
        response = auth_session.get(
            f"{BASE_URL}/api/ai-predictions/cancel-risk/default?days_ahead=60&min_score=30"
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "rows" in data
        assert data.get("window_days") == 60, "window_days should match days_ahead param"
        
        # Verify each row has required fields
        for row in data["rows"][:5]:  # Check first 5 rows
            assert "score" in row, "Row should have 'score'"
            assert "band" in row, "Row should have 'band'"
            assert "signals" in row, "Row should have 'signals'"
            assert 0 <= row["score"] <= 100, f"Score should be 0-100, got {row['score']}"
            assert row["band"] in ["high", "medium", "low"], f"Invalid band: {row['band']}"
            
            # Verify signals structure
            for signal in row["signals"]:
                assert "name" in signal, "Signal should have 'name'"
                assert "impact" in signal, "Signal should have 'impact'"
        
        print(f"Filtered cancel risk: {len(data['rows'])} rows with min_score=30")
    
    def test_cancel_risk_signals_sum_approximates_score(self, auth_session):
        """Verify signals impact sum is close to final score (baseline 30 + signals)"""
        response = auth_session.get(
            f"{BASE_URL}/api/ai-predictions/cancel-risk/default?days_ahead=60&min_score=30"
        )
        assert response.status_code == 200
        
        data = response.json()
        if len(data["rows"]) > 0:
            row = data["rows"][0]
            signals_sum = sum(s["impact"] for s in row["signals"])
            expected_score = max(0, min(100, 30 + signals_sum))  # baseline 30
            # Allow some tolerance due to clamping
            assert abs(row["score"] - expected_score) <= 5, \
                f"Score {row['score']} should be close to baseline(30) + signals({signals_sum}) = {expected_score}"
            print(f"Score validation: score={row['score']}, signals_sum={signals_sum}, expected~{expected_score}")


class TestCancelRiskBooking:
    """Test GET /api/ai-predictions/cancel-risk/booking/{booking_id}"""
    
    def test_cancel_risk_single_booking(self, auth_session):
        """Test getting cancel risk for a specific booking"""
        # First get a booking_id from the list
        list_response = auth_session.get(
            f"{BASE_URL}/api/ai-predictions/cancel-risk/default?min_score=0"
        )
        if list_response.status_code != 200 or len(list_response.json().get("rows", [])) == 0:
            pytest.skip("No bookings available for testing")
        
        booking_id = list_response.json()["rows"][0]["booking_id"]
        
        response = auth_session.get(
            f"{BASE_URL}/api/ai-predictions/cancel-risk/booking/{booking_id}"
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "score" in data, "Response should have 'score'"
        assert "band" in data, "Response should have 'band'"
        assert "signals" in data, "Response should have 'signals'"
        
        print(f"Single booking risk: booking_id={booking_id}, score={data['score']}, band={data['band']}")
    
    def test_cancel_risk_nonexistent_booking(self, auth_session):
        """Test 404 for non-existent booking"""
        response = auth_session.get(
            f"{BASE_URL}/api/ai-predictions/cancel-risk/booking/nonexistent-booking-id-12345"
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("Non-existent booking correctly returns 404")


class TestSaveOffer:
    """Test POST /api/ai-predictions/cancel-risk/{booking_id}/save-offer"""
    
    def test_save_offer_success(self, auth_session):
        """Test queuing a save-offer for a booking"""
        # Get a booking_id
        list_response = auth_session.get(
            f"{BASE_URL}/api/ai-predictions/cancel-risk/default?min_score=0"
        )
        if list_response.status_code != 200 or len(list_response.json().get("rows", [])) == 0:
            pytest.skip("No bookings available for testing")
        
        booking_id = list_response.json()["rows"][0]["booking_id"]
        
        response = auth_session.post(
            f"{BASE_URL}/api/ai-predictions/cancel-risk/{booking_id}/save-offer"
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify response structure
        assert "voucher_code" in data, "Response should have 'voucher_code'"
        assert data["voucher_code"].startswith("STAY-"), f"Voucher should start with STAY-, got {data['voucher_code']}"
        assert data.get("discount_pct") == 10, f"Discount should be 10%, got {data.get('discount_pct')}"
        assert data.get("status") == "queued", f"Status should be 'queued', got {data.get('status')}"
        
        print(f"Save-offer queued: voucher={data['voucher_code']}, discount={data['discount_pct']}%")
    
    def test_save_offer_nonexistent_booking(self, auth_session):
        """Test 404 for save-offer on non-existent booking"""
        response = auth_session.post(
            f"{BASE_URL}/api/ai-predictions/cancel-risk/nonexistent-booking-id-12345/save-offer"
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("Save-offer on non-existent booking correctly returns 404")


class TestUpsellList:
    """Test GET /api/ai-predictions/upsell/{property_id}"""
    
    def test_upsell_list_default(self, auth_session):
        """Test upsell list with default params"""
        response = auth_session.get(
            f"{BASE_URL}/api/ai-predictions/upsell/default?days_ahead=14&min_score=40"
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify response structure
        assert "rows" in data, "Response should have 'rows'"
        assert "by_top_recommendation" in data, "Response should have 'by_top_recommendation'"
        assert "count" in data, "Response should have 'count'"
        
        # Verify each row has required fields
        for row in data["rows"][:5]:
            assert "scores" in row, "Row should have 'scores'"
            assert "top_recommendation" in row, "Row should have 'top_recommendation'"
            assert "top_score" in row, "Row should have 'top_score'"
            
            # Verify scores has 5 categories
            scores = row["scores"]
            expected_cats = ["room_upgrade", "late_checkout", "breakfast", "spa", "transport"]
            for cat in expected_cats:
                assert cat in scores, f"Scores should have '{cat}'"
                assert 0 <= scores[cat] <= 100, f"Score for {cat} should be 0-100"
        
        print(f"Upsell list: {data['count']} rows, by_top_recommendation={data.get('by_top_recommendation')}")
    
    def test_upsell_list_category_filter(self, auth_session):
        """Test upsell list filtered by category=late_checkout"""
        response = auth_session.get(
            f"{BASE_URL}/api/ai-predictions/upsell/default?category=late_checkout&min_score=40"
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("category_filter") == "late_checkout", "category_filter should be 'late_checkout'"
        
        # Verify rows are sorted by late_checkout score (descending)
        rows = data["rows"]
        if len(rows) >= 2:
            for i in range(len(rows) - 1):
                score_current = rows[i]["scores"]["late_checkout"]
                score_next = rows[i + 1]["scores"]["late_checkout"]
                assert score_current >= score_next, \
                    f"Rows should be sorted by late_checkout score desc: {score_current} >= {score_next}"
        
        print(f"Category filter test: {len(rows)} rows sorted by late_checkout score")


class TestUpsellSendOffer:
    """Test POST /api/ai-predictions/upsell/{booking_id}/send-offer"""
    
    def test_upsell_send_offer_success(self, auth_session):
        """Test sending upsell offer for late_checkout"""
        # Get a booking_id
        list_response = auth_session.get(
            f"{BASE_URL}/api/ai-predictions/upsell/default?min_score=0"
        )
        if list_response.status_code != 200 or len(list_response.json().get("rows", [])) == 0:
            pytest.skip("No bookings available for testing")
        
        booking_id = list_response.json()["rows"][0]["booking_id"]
        
        response = auth_session.post(
            f"{BASE_URL}/api/ai-predictions/upsell/{booking_id}/send-offer?category=late_checkout"
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "offer_id" in data, "Response should have 'offer_id'"
        assert data["offer_id"].startswith("UP-"), f"Offer ID should start with UP-, got {data['offer_id']}"
        assert data.get("status") == "queued", f"Status should be 'queued', got {data.get('status')}"
        assert data.get("category") == "late_checkout", f"Category should be 'late_checkout'"
        
        print(f"Upsell offer queued: offer_id={data['offer_id']}, category={data['category']}")
    
    def test_upsell_send_offer_invalid_category(self, auth_session):
        """Test 400 for invalid category"""
        # Get a booking_id
        list_response = auth_session.get(
            f"{BASE_URL}/api/ai-predictions/upsell/default?min_score=0"
        )
        if list_response.status_code != 200 or len(list_response.json().get("rows", [])) == 0:
            pytest.skip("No bookings available for testing")
        
        booking_id = list_response.json()["rows"][0]["booking_id"]
        
        response = auth_session.post(
            f"{BASE_URL}/api/ai-predictions/upsell/{booking_id}/send-offer?category=invalid_category"
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("Invalid category correctly returns 400")
    
    def test_upsell_send_offer_nonexistent_booking(self, auth_session):
        """Test 404 for non-existent booking"""
        response = auth_session.post(
            f"{BASE_URL}/api/ai-predictions/upsell/nonexistent-booking-id-12345/send-offer?category=breakfast"
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("Upsell offer on non-existent booking correctly returns 404")


class TestRegressionSmoke:
    """Regression smoke tests for previous batches"""
    
    def test_tr_compliance_accessible(self, auth_session):
        """Verify TR Compliance endpoints still work"""
        response = auth_session.get(f"{BASE_URL}/api/tr-compliance/kbs/default/history")
        assert response.status_code == 200, f"TR Compliance KBS history should return 200, got {response.status_code}"
        print("TR Compliance KBS history: PASSED")
    
    def test_today_hub_accessible(self, auth_session):
        """Verify Today Hub data endpoints still work"""
        response = auth_session.get(f"{BASE_URL}/api/tier1-dashboard/default?days=7")
        assert response.status_code == 200, f"Tier1 dashboard should return 200, got {response.status_code}"
        print("Tier1 Dashboard (Today Hub): PASSED")
    
    def test_morning_brief_accessible(self, auth_session):
        """Verify Morning Brief endpoint still works"""
        response = auth_session.get(f"{BASE_URL}/api/morning-brief/default")
        assert response.status_code == 200, f"Morning brief should return 200, got {response.status_code}"
        print("Morning Brief: PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
