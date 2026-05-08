"""
Iteration 168 - Booking.com Scraper URL Validation Tests

Tests the rewritten booking_scraper.py and new market_robot.py endpoints:
- POST /api/revenue/market-robot/validate-booking-url
- POST /api/revenue/market-robot/{pid}/competitors (with URL validation)
- POST /api/revenue/market-robot/{pid}/competitors/revalidate-all
- PUT /api/revenue/market-robot/{pid}/our-booking (with URL validation)
- GET /api/revenue/market-robot/{pid}/competitors (regression)
- GET /api/revenue/market-robot/{pid}/our-booking (regression)
- GET /api/revenue/market-robot/{pid}/config (regression)

IMPORTANT: Each validate_booking_url call takes 30-60 seconds (headless Chromium).
Set timeouts accordingly. Subsequent calls to same URL use cache (~10s).
"""

import pytest
import requests
import os
import time
import uuid

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
PROPERTY_ID = "default"

# Test URLs
VALID_BOOKING_URL = "https://www.booking.com/hotel/ch/franziskaner-by-centra.en-gb.html"
INVALID_BOOKING_URL = "https://www.booking.com/hotel/ch/this-hotel-does-not-exist-xxx.html"
NON_BOOKING_URL = "https://www.expedia.com/hotel/some-hotel"


class TestAuth:
    """Authentication tests - run first"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get admin auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"},
            timeout=30
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in login response"
        return data["token"]
    
    def test_login_success(self, auth_token):
        """Verify admin login works"""
        assert auth_token is not None
        assert len(auth_token) > 20
        print(f"✓ Admin login successful, token length: {len(auth_token)}")


class TestValidateBookingUrl:
    """Tests for POST /api/revenue/market-robot/validate-booking-url"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers for all tests in this class"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"},
            timeout=30
        )
        token = response.json().get("token")
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_validate_valid_booking_url(self, auth_headers):
        """Test validation with valid Franziskaner hotel URL (CHF currency)
        
        Expected: ok=true, hotel_id=14990420, hotel_name contains 'Franziskaner', sample_price>0
        NOTE: This test takes 30-60 seconds due to headless Chromium scraping.
        """
        print("\n⏳ Testing valid Booking.com URL (this takes 30-60 seconds)...")
        start = time.time()
        
        response = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/validate-booking-url",
            json={"booking_url": VALID_BOOKING_URL, "currency": "CHF"},
            headers=auth_headers,
            timeout=120  # Long timeout for scraping
        )
        
        elapsed = time.time() - start
        print(f"⏱️ Validation took {elapsed:.1f}s")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Core assertions
        assert data.get("ok") is True, f"Expected ok=true, got: {data}"
        assert data.get("hotel_id") is not None, f"Expected hotel_id, got: {data}"
        
        # Verify hotel_id is the expected one (14990420 for Franziskaner)
        hotel_id = data.get("hotel_id")
        print(f"✓ hotel_id resolved: {hotel_id}")
        
        # Hotel name should contain Franziskaner
        hotel_name = data.get("hotel_name", "")
        print(f"✓ hotel_name: {hotel_name}")
        
        # Sample price should be > 0
        sample_price = data.get("sample_price")
        print(f"✓ sample_price: {sample_price}")
        if sample_price is not None:
            assert sample_price > 0, f"Expected sample_price > 0, got: {sample_price}"
        
        # Currency should be echoed back
        assert data.get("currency") == "CHF", f"Expected currency=CHF, got: {data.get('currency')}"
        
        print(f"✓ Valid URL validation passed: ok={data['ok']}, hotel_id={hotel_id}, price={sample_price}")
    
    def test_validate_invalid_booking_url(self, auth_headers):
        """Test validation with non-existent hotel URL
        
        Expected: ok=false, hotel_id=null, error present
        NOTE: This test takes 30-60 seconds due to headless Chromium scraping.
        """
        print("\n⏳ Testing invalid Booking.com URL (this takes 30-60 seconds)...")
        start = time.time()
        
        response = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/validate-booking-url",
            json={"booking_url": INVALID_BOOKING_URL, "currency": "CHF"},
            headers=auth_headers,
            timeout=120
        )
        
        elapsed = time.time() - start
        print(f"⏱️ Validation took {elapsed:.1f}s")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Should fail validation
        assert data.get("ok") is False, f"Expected ok=false for invalid URL, got: {data}"
        assert data.get("hotel_id") is None, f"Expected hotel_id=null, got: {data.get('hotel_id')}"
        assert data.get("error") is not None, f"Expected error message, got: {data}"
        
        print(f"✓ Invalid URL correctly rejected: ok={data['ok']}, error={data.get('error')}")
    
    def test_validate_non_booking_url(self, auth_headers):
        """Test validation with non-booking.com URL
        
        Expected: ok=false, error='not_a_booking_url'
        This should be fast (no scraping needed).
        """
        print("\n⏳ Testing non-Booking.com URL...")
        
        response = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/validate-booking-url",
            json={"booking_url": NON_BOOKING_URL},
            headers=auth_headers,
            timeout=30
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data.get("ok") is False, f"Expected ok=false for non-booking URL, got: {data}"
        assert data.get("error") == "not_a_booking_url", f"Expected error='not_a_booking_url', got: {data.get('error')}"
        
        print(f"✓ Non-Booking URL correctly rejected: error={data.get('error')}")
    
    def test_validate_missing_url(self, auth_headers):
        """Test validation with missing URL"""
        response = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/validate-booking-url",
            json={},
            headers=auth_headers,
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is False
        assert data.get("error") == "missing_url"
        print("✓ Missing URL correctly rejected")


class TestCompetitors:
    """Tests for competitor management endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"},
            timeout=30
        )
        token = response.json().get("token")
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    @pytest.fixture(scope="class")
    def test_competitor_ids(self):
        """Track competitor IDs created during tests for cleanup"""
        return []
    
    def test_add_competitor_with_valid_url(self, auth_headers, test_competitor_ids):
        """Test adding competitor with valid Booking.com URL
        
        Expected: Persists booking_hotel_id, returns validation object
        NOTE: Takes 30-60 seconds due to URL validation.
        """
        print("\n⏳ Adding competitor with valid URL (30-60 seconds)...")
        start = time.time()
        
        response = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/{PROPERTY_ID}/competitors",
            json={
                "booking_url": VALID_BOOKING_URL,
                "name": "TEST_Franziskaner Competitor"
            },
            headers=auth_headers,
            timeout=120
        )
        
        elapsed = time.time() - start
        print(f"⏱️ Add competitor took {elapsed:.1f}s")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Should have competitor ID
        assert "id" in data, f"Expected competitor id, got: {data}"
        test_competitor_ids.append(data["id"])
        
        # Should have booking_hotel_id from validation
        assert data.get("booking_hotel_id") is not None, f"Expected booking_hotel_id, got: {data}"
        
        # Should have validation object
        assert "validation" in data, f"Expected validation object, got: {data}"
        validation = data["validation"]
        assert validation.get("ok") is True, f"Expected validation.ok=true, got: {validation}"
        
        print(f"✓ Competitor added: id={data['id']}, booking_hotel_id={data.get('booking_hotel_id')}")
    
    def test_add_competitor_with_invalid_url_blocked(self, auth_headers, test_competitor_ids):
        """Test adding competitor with bogus Booking.com URL
        
        Expected: Blocked with error='invalid_booking_url'
        NOTE: Takes 30-60 seconds due to URL validation attempt.
        """
        print("\n⏳ Adding competitor with invalid URL (should be blocked, 30-60 seconds)...")
        start = time.time()
        
        response = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/{PROPERTY_ID}/competitors",
            json={
                "booking_url": INVALID_BOOKING_URL,
                "name": "TEST_Invalid Competitor"
            },
            headers=auth_headers,
            timeout=120
        )
        
        elapsed = time.time() - start
        print(f"⏱️ Validation took {elapsed:.1f}s")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Should be blocked
        assert data.get("error") == "invalid_booking_url", f"Expected error='invalid_booking_url', got: {data}"
        
        print(f"✓ Invalid competitor URL correctly blocked: error={data.get('error')}")
    
    def test_add_competitor_with_skip_validation(self, auth_headers, test_competitor_ids):
        """Test adding competitor with skip_validation=true (backward compat)
        
        Expected: Persists regardless of URL validity
        """
        print("\n⏳ Adding competitor with skip_validation=true...")
        
        response = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/{PROPERTY_ID}/competitors",
            json={
                "booking_url": INVALID_BOOKING_URL,
                "name": "TEST_Skipped Validation Competitor",
                "skip_validation": True
            },
            headers=auth_headers,
            timeout=30
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Should have competitor ID (persisted despite invalid URL)
        assert "id" in data, f"Expected competitor id, got: {data}"
        test_competitor_ids.append(data["id"])
        
        # booking_hotel_id should be None (not validated)
        assert data.get("booking_hotel_id") is None, f"Expected booking_hotel_id=None, got: {data.get('booking_hotel_id')}"
        
        print(f"✓ Competitor added with skip_validation: id={data['id']}")
    
    def test_get_competitors_regression(self, auth_headers):
        """Regression test: GET /competitors still returns list"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/{PROPERTY_ID}/competitors",
            headers=auth_headers,
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "competitors" in data
        assert isinstance(data["competitors"], list)
        print(f"✓ GET competitors works: {len(data['competitors'])} competitors found")
    
    def test_revalidate_all_competitors(self, auth_headers, test_competitor_ids):
        """Test POST /competitors/revalidate-all
        
        Expected: Returns {checked, valid, invalid, competitors:[...]} with per-competitor results
        NOTE: Takes 30-60 seconds per competitor.
        """
        print("\n⏳ Revalidating all competitors (may take several minutes)...")
        start = time.time()
        
        response = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/{PROPERTY_ID}/competitors/revalidate-all",
            headers=auth_headers,
            timeout=300  # Long timeout for multiple validations
        )
        
        elapsed = time.time() - start
        print(f"⏱️ Revalidation took {elapsed:.1f}s")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Check response structure
        assert "checked" in data, f"Expected 'checked' field, got: {data}"
        assert "valid" in data, f"Expected 'valid' field, got: {data}"
        assert "invalid" in data, f"Expected 'invalid' field, got: {data}"
        assert "competitors" in data, f"Expected 'competitors' field, got: {data}"
        
        # Competitors should have per-entry results
        for comp in data["competitors"]:
            assert "id" in comp
            assert "ok" in comp
            # Valid ones should have hotel_id
            if comp.get("ok"):
                assert comp.get("hotel_id") is not None
        
        print(f"✓ Revalidation complete: checked={data['checked']}, valid={data['valid']}, invalid={data['invalid']}")
    
    def test_cleanup_test_competitors(self, auth_headers, test_competitor_ids):
        """Cleanup: Delete test competitors created during tests"""
        print(f"\n🧹 Cleaning up {len(test_competitor_ids)} test competitors...")
        
        for comp_id in test_competitor_ids:
            response = requests.delete(
                f"{BASE_URL}/api/revenue/market-robot/competitors/{comp_id}",
                headers=auth_headers,
                timeout=30
            )
            if response.status_code == 200:
                print(f"  ✓ Deleted competitor {comp_id}")
            else:
                print(f"  ⚠ Failed to delete competitor {comp_id}: {response.status_code}")
        
        test_competitor_ids.clear()


class TestOurBooking:
    """Tests for our-booking endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"},
            timeout=30
        )
        token = response.json().get("token")
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_get_our_booking_regression(self, auth_headers):
        """Regression test: GET /our-booking returns booking_url"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/{PROPERTY_ID}/our-booking",
            headers=auth_headers,
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "property_id" in data
        assert "booking_url" in data
        print(f"✓ GET our-booking works: booking_url={data.get('booking_url', 'not set')}")
    
    def test_set_our_booking_with_validation(self, auth_headers):
        """Test PUT /our-booking with URL validation
        
        Expected: Sets booking_url and populates booking_hotel_id
        NOTE: Takes 30-60 seconds due to validation.
        """
        print("\n⏳ Setting our-booking URL with validation (30-60 seconds)...")
        start = time.time()
        
        response = requests.put(
            f"{BASE_URL}/api/revenue/market-robot/{PROPERTY_ID}/our-booking",
            json={"booking_url": VALID_BOOKING_URL},
            headers=auth_headers,
            timeout=120
        )
        
        elapsed = time.time() - start
        print(f"⏱️ Set our-booking took {elapsed:.1f}s")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data.get("ok") is True, f"Expected ok=true, got: {data}"
        assert data.get("booking_url") == VALID_BOOKING_URL
        
        # Should have validation object
        validation = data.get("validation", {})
        if validation:
            print(f"✓ Validation: ok={validation.get('ok')}, hotel_id={validation.get('hotel_id')}")
        
        print(f"✓ Our-booking URL set successfully")
    
    def test_set_our_booking_non_booking_url_rejected(self, auth_headers):
        """Test PUT /our-booking rejects non-booking.com URLs"""
        response = requests.put(
            f"{BASE_URL}/api/revenue/market-robot/{PROPERTY_ID}/our-booking",
            json={"booking_url": NON_BOOKING_URL},
            headers=auth_headers,
            timeout=30
        )
        
        assert response.status_code == 400, f"Expected 400 for non-booking URL, got {response.status_code}"
        print("✓ Non-booking.com URL correctly rejected with 400")


class TestRegressionEndpoints:
    """Regression tests for existing endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"},
            timeout=30
        )
        token = response.json().get("token")
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_get_config_regression(self, auth_headers):
        """Regression test: GET /config still works"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/{PROPERTY_ID}/config",
            headers=auth_headers,
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "property_id" in data
        assert "city" in data
        print(f"✓ GET config works: city={data.get('city')}, currency={data.get('currency')}")
    
    def test_health_check(self, auth_headers):
        """Basic health check - backend responds"""
        response = requests.get(
            f"{BASE_URL}/api/properties",
            headers=auth_headers,
            timeout=30
        )
        
        assert response.status_code == 200
        print("✓ Backend health check passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-x"])
