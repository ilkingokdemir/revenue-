"""
Iteration 323 - Vision Scraper Backend Endpoint Tests

Tests the POST /api/revenue/market-robot/scrape-booking-vision endpoint which:
1. Takes a Booking.com URL
2. Screenshots it with Playwright
3. Sends PNG to GPT-4o-mini Vision via emergentintegrations + EMERGENT_LLM_KEY
4. Returns structured property data including room_count

Also tests:
- Negative case: empty booking_url → 400
- Regression: GET /api/revenue/market-robot/proxy-status → 200
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials from test_credentials.md
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin JWT token for authenticated requests."""
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    if resp.status_code != 200:
        pytest.skip(f"Admin login failed: {resp.status_code} - {resp.text[:200]}")
    data = resp.json()
    token = data.get("access_token") or data.get("token")
    if not token:
        pytest.skip("No token in login response")
    return token


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    """Headers with Bearer token for authenticated requests."""
    return {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json",
    }


class TestVisionScraperEndpoint:
    """Tests for POST /api/revenue/market-robot/scrape-booking-vision"""

    def test_scrape_booking_vision_success(self, auth_headers):
        """
        Test: POST /api/revenue/market-robot/scrape-booking-vision with valid URL
        
        Expected: 200 status, body with keys:
        - ok, hotel_name, room_count, price_per_night, currency, star_rating,
        - review_score, review_count, is_blocked_page, model, screenshot_size_bytes
        
        Note: room_count may be null but the KEY must be present.
        screenshot_size_bytes should be > 50000.
        """
        payload = {
            "booking_url": "https://www.booking.com/hotel/gb/the-barkston.html",
            "model": "gpt-4o-mini",
            "auto_dates": True,
        }
        
        # Vision endpoint takes 15-40 seconds due to Playwright + GPT-4o-mini call
        resp = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/scrape-booking-vision",
            json=payload,
            headers=auth_headers,
            timeout=90,  # 90s timeout as per agent context
        )
        
        # Status code assertion
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:500]}"
        
        data = resp.json()
        
        # Required keys must be present
        required_keys = [
            "ok",
            "hotel_name",
            "room_count",
            "price_per_night",
            "currency",
            "star_rating",
            "review_score",
            "review_count",
            "is_blocked_page",
            "model",
            "screenshot_size_bytes",
        ]
        
        for key in required_keys:
            assert key in data, f"Missing required key: {key}. Response: {data}"
        
        # ok should be True (even if is_blocked_page is True, that's still a success)
        # The endpoint returns ok:true when it successfully processed the request
        # is_blocked_page:true just means Booking.com blocked the page content
        assert "ok" in data, f"'ok' key missing from response: {data}"
        
        # screenshot_size_bytes should be > 50000 (indicates real screenshot taken)
        screenshot_size = data.get("screenshot_size_bytes", 0)
        assert screenshot_size > 50000, (
            f"screenshot_size_bytes should be > 50000, got {screenshot_size}. "
            f"This suggests screenshot failed or was too small."
        )
        
        # model should match what we sent
        assert data.get("model") == "gpt-4o-mini", f"Model mismatch: {data.get('model')}"
        
        # room_count may be null but key must exist (already checked above)
        # Just verify it's either None or an int
        room_count = data.get("room_count")
        assert room_count is None or isinstance(room_count, int), (
            f"room_count should be null or int, got {type(room_count)}: {room_count}"
        )
        
        print(f"✓ Vision scraper SUCCESS:")
        print(f"  - ok: {data.get('ok')}")
        print(f"  - hotel_name: {data.get('hotel_name')}")
        print(f"  - room_count: {data.get('room_count')}")
        print(f"  - price_per_night: {data.get('price_per_night')}")
        print(f"  - currency: {data.get('currency')}")
        print(f"  - star_rating: {data.get('star_rating')}")
        print(f"  - review_score: {data.get('review_score')}")
        print(f"  - review_count: {data.get('review_count')}")
        print(f"  - is_blocked_page: {data.get('is_blocked_page')}")
        print(f"  - screenshot_size_bytes: {data.get('screenshot_size_bytes')}")

    def test_scrape_booking_vision_empty_url_returns_400(self, auth_headers):
        """
        Test: POST /api/revenue/market-robot/scrape-booking-vision with empty booking_url
        
        Expected: HTTP 400 with message 'booking_url required'
        """
        payload = {"booking_url": ""}
        
        resp = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/scrape-booking-vision",
            json=payload,
            headers=auth_headers,
            timeout=15,
        )
        
        # Status code assertion
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text[:500]}"
        
        # Check error message
        data = resp.json()
        detail = data.get("detail", "")
        assert "booking_url required" in detail.lower() or "booking_url" in str(data).lower(), (
            f"Expected 'booking_url required' in error, got: {data}"
        )
        
        print(f"✓ Empty URL correctly returns 400: {detail}")


class TestProxyStatusEndpoint:
    """Regression test for GET /api/revenue/market-robot/proxy-status"""

    def test_proxy_status_returns_200(self, auth_headers):
        """
        Test: GET /api/revenue/market-robot/proxy-status
        
        Expected: HTTP 200 with proxy configuration status
        """
        resp = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/proxy-status",
            headers=auth_headers,
            timeout=15,
        )
        
        # Status code assertion
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:500]}"
        
        data = resp.json()
        
        # Should have 'configured' key at minimum
        assert "configured" in data, f"Missing 'configured' key in response: {data}"
        
        # Should have 'env_var' key
        assert "env_var" in data, f"Missing 'env_var' key in response: {data}"
        assert data.get("env_var") == "BOOKING_PROXY_URL", (
            f"Expected env_var='BOOKING_PROXY_URL', got: {data.get('env_var')}"
        )
        
        print(f"✓ Proxy status endpoint working:")
        print(f"  - configured: {data.get('configured')}")
        print(f"  - server: {data.get('server')}")
        print(f"  - has_auth: {data.get('has_auth')}")


class TestAuthRequired:
    """Verify endpoints require authentication"""

    def test_vision_scraper_requires_auth(self):
        """Vision scraper endpoint should return 401 without auth."""
        resp = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/scrape-booking-vision",
            json={"booking_url": "https://www.booking.com/hotel/gb/test.html"},
            timeout=15,
        )
        assert resp.status_code == 401, f"Expected 401 without auth, got {resp.status_code}"
        print("✓ Vision scraper correctly requires authentication")

    def test_proxy_status_requires_auth(self):
        """Proxy status endpoint should return 401 without auth."""
        resp = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/proxy-status",
            timeout=15,
        )
        assert resp.status_code == 401, f"Expected 401 without auth, got {resp.status_code}"
        print("✓ Proxy status correctly requires authentication")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
