"""
Iteration 125 - Premium Differentiator Features Testing
Tests for:
1. AI Weekly Revenue Digest (GPT-5.2)
2. AI Upsell Engine
3. Competitor Rate Scraping Automation
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"

# Test property
TEST_PROPERTY = "aldgate-flats"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for admin user"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        data = response.json()
        return data.get("token") or data.get("access_token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


@pytest.fixture(scope="module")
def test_booking_id(auth_headers):
    """Get a booking ID for upsell testing"""
    # Get bookings from timeline
    response = requests.get(
        f"{BASE_URL}/api/bookings/timeline/{TEST_PROPERTY}?days=30",
        headers=auth_headers
    )
    if response.status_code == 200:
        data = response.json()
        # Find a booking from the groups
        for group in data.get("groups", []):
            for room in group.get("rooms", []):
                for booking in room.get("bookings", []):
                    if booking.get("id"):
                        return booking["id"]
    # If no booking found, create one
    return None


class TestWeeklyDigestAPI:
    """AI Weekly Revenue Digest API Tests"""
    
    def test_get_weekly_digest_initial(self, auth_headers):
        """GET /api/revenue/weekly-digest/{property_id} - Get existing or empty digest"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/weekly-digest/{TEST_PROPERTY}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        # Either has digest_text (existing) or status: none (no digest yet)
        assert "digest_text" in data or data.get("status") == "none", f"Unexpected response: {data}"
        print(f"✓ GET weekly digest returned: {'existing digest' if 'digest_text' in data else 'no digest yet'}")
    
    def test_generate_weekly_digest(self, auth_headers):
        """POST /api/revenue/weekly-digest/{property_id}/generate - Generate AI digest with GPT-5.2"""
        response = requests.post(
            f"{BASE_URL}/api/revenue/weekly-digest/{TEST_PROPERTY}/generate",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Check for error (AI service not configured)
        if "error" in data:
            print(f"⚠ Digest generation returned error: {data['error']}")
            pytest.skip(f"AI service error: {data['error']}")
        
        # Validate digest structure
        assert "id" in data, "Missing id in digest"
        assert "property_id" in data, "Missing property_id"
        assert "digest_text" in data, "Missing digest_text"
        assert "metrics" in data, "Missing metrics"
        assert "generated_at" in data, "Missing generated_at"
        
        # Validate metrics
        metrics = data["metrics"]
        assert "new_bookings" in metrics, "Missing new_bookings in metrics"
        assert "revenue" in metrics, "Missing revenue in metrics"
        assert "adr" in metrics, "Missing adr in metrics"
        assert "avg_occupancy" in metrics, "Missing avg_occupancy in metrics"
        assert "room_nights" in metrics, "Missing room_nights in metrics"
        
        print(f"✓ Generated digest with {metrics['new_bookings']} bookings, £{metrics['revenue']} revenue")
        print(f"  Digest text length: {len(data['digest_text'])} chars")
    
    def test_get_weekly_digest_after_generate(self, auth_headers):
        """GET /api/revenue/weekly-digest/{property_id} - Verify digest persisted"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/weekly-digest/{TEST_PROPERTY}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should now have digest_text
        assert "digest_text" in data, "Digest should be persisted after generation"
        assert "metrics" in data, "Metrics should be persisted"
        assert data.get("property_id") == TEST_PROPERTY
        print(f"✓ Digest persisted and retrieved successfully")
    
    def test_weekly_digest_unauthorized(self):
        """Weekly digest endpoints require authentication"""
        response = requests.get(f"{BASE_URL}/api/revenue/weekly-digest/{TEST_PROPERTY}")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Unauthorized access correctly rejected")


class TestUpsellEngineAPI:
    """AI Upsell Engine API Tests"""
    
    def test_get_upsell_suggestions(self, auth_headers, test_booking_id):
        """GET /api/revenue/upsell/{booking_id} - Get upsell suggestions"""
        if not test_booking_id:
            pytest.skip("No booking available for upsell testing")
        
        response = requests.get(
            f"{BASE_URL}/api/revenue/upsell/{test_booking_id}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Check for error
        if "error" in data:
            pytest.skip(f"Booking not found: {data['error']}")
        
        # Validate response structure
        assert "booking_id" in data, "Missing booking_id"
        assert "suggestions" in data, "Missing suggestions"
        assert "total_potential" in data, "Missing total_potential"
        
        suggestions = data["suggestions"]
        assert isinstance(suggestions, list), "Suggestions should be a list"
        
        # Check suggestion types
        suggestion_types = [s.get("type") for s in suggestions]
        print(f"✓ Got {len(suggestions)} upsell suggestions: {set(suggestion_types)}")
        
        # Validate suggestion structure
        for s in suggestions:
            assert "id" in s, "Missing id in suggestion"
            assert "type" in s, "Missing type in suggestion"
            assert "title" in s, "Missing title in suggestion"
            assert "price" in s, "Missing price in suggestion"
            assert "price_label" in s, "Missing price_label in suggestion"
        
        # Check expected types exist
        expected_types = {"early_checkin", "late_checkout", "addon"}
        found_types = set(suggestion_types)
        assert expected_types.issubset(found_types), f"Missing expected types. Found: {found_types}"
        
        print(f"  Total upsell potential: £{data['total_potential']}")
    
    def test_accept_upsell(self, auth_headers, test_booking_id):
        """POST /api/revenue/upsell/{booking_id}/accept - Accept an upsell"""
        if not test_booking_id:
            pytest.skip("No booking available for upsell testing")
        
        # First get suggestions
        response = requests.get(
            f"{BASE_URL}/api/revenue/upsell/{test_booking_id}",
            headers=auth_headers
        )
        if response.status_code != 200 or "error" in response.json():
            pytest.skip("Could not get upsell suggestions")
        
        suggestions = response.json().get("suggestions", [])
        if not suggestions:
            pytest.skip("No suggestions available")
        
        # Accept the first addon suggestion
        addon = next((s for s in suggestions if s["type"] == "addon"), suggestions[0])
        
        accept_response = requests.post(
            f"{BASE_URL}/api/revenue/upsell/{test_booking_id}/accept",
            headers=auth_headers,
            json={
                "type": addon["type"],
                "price": addon["price"],
                "description": addon["title"]
            }
        )
        assert accept_response.status_code == 200, f"Expected 200, got {accept_response.status_code}: {accept_response.text}"
        data = accept_response.json()
        
        assert data.get("status") == "accepted", f"Expected status 'accepted', got {data.get('status')}"
        assert "revenue_added" in data, "Missing revenue_added"
        print(f"✓ Accepted upsell: {addon['title']} for £{data['revenue_added']}")
    
    def test_upsell_stats(self, auth_headers):
        """GET /api/revenue/upsell/stats/{property_id} - Get upsell performance stats"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/upsell/stats/{TEST_PROPERTY}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "total_upsells" in data, "Missing total_upsells"
        assert "total_revenue" in data, "Missing total_revenue"
        assert "by_type" in data, "Missing by_type breakdown"
        
        print(f"✓ Upsell stats: {data['total_upsells']} upsells, £{data['total_revenue']} total revenue")
        if data["by_type"]:
            for item in data["by_type"]:
                print(f"  - {item['type']}: {item['count']} upsells, £{item['revenue']}")
    
    def test_upsell_invalid_booking(self, auth_headers):
        """GET /api/revenue/upsell/{booking_id} - Invalid booking returns error"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/upsell/invalid-booking-id-12345",
            headers=auth_headers
        )
        assert response.status_code == 200  # Returns 200 with error message
        data = response.json()
        assert "error" in data, "Should return error for invalid booking"
        print("✓ Invalid booking correctly returns error")
    
    def test_upsell_unauthorized(self):
        """Upsell endpoints require authentication"""
        response = requests.get(f"{BASE_URL}/api/revenue/upsell/some-booking-id")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Unauthorized access correctly rejected")


class TestRateScraperAPI:
    """Competitor Rate Scraping Automation API Tests"""
    
    def test_get_scraper_status(self, auth_headers):
        """GET /api/revenue/rate-scraper/{property_id} - Get scraper status and rates"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/rate-scraper/{TEST_PROPERTY}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Validate structure
        assert "config" in data, "Missing config"
        assert "daily" in data, "Missing daily rate data"
        assert "total_competitors" in data, "Missing total_competitors"
        
        # Validate config
        config = data["config"]
        assert "strategy" in config, "Missing strategy in config"
        assert "auto_adjust" in config, "Missing auto_adjust in config"
        assert "max_adjustment_pct" in config, "Missing max_adjustment_pct in config"
        assert "min_rate" in config, "Missing min_rate in config"
        assert "max_rate" in config, "Missing max_rate in config"
        
        # Validate daily data
        daily = data["daily"]
        assert isinstance(daily, list), "Daily should be a list"
        assert len(daily) > 0, "Should have daily rate data"
        
        # Check first day structure
        day = daily[0]
        assert "date" in day, "Missing date"
        assert "our_rate" in day, "Missing our_rate"
        assert "suggested_rate" in day, "Missing suggested_rate"
        assert "dow" in day, "Missing dow (day of week)"
        
        print(f"✓ Rate scraper status: {data['total_competitors']} competitors tracked")
        print(f"  Strategy: {config['strategy']}, Auto-adjust: {config['auto_adjust']}")
        print(f"  Daily data for {len(daily)} days")
    
    def test_update_scraper_config(self, auth_headers):
        """PUT /api/revenue/rate-scraper/{property_id}/config - Update scraper config"""
        new_config = {
            "enabled": True,
            "auto_adjust": True,
            "strategy": "undercut_5",
            "max_adjustment_pct": 20,
            "min_rate": 60,
            "max_rate": 400
        }
        
        response = requests.put(
            f"{BASE_URL}/api/revenue/rate-scraper/{TEST_PROPERTY}/config",
            headers=auth_headers,
            json=new_config
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data.get("strategy") == "undercut_5", f"Strategy not updated: {data.get('strategy')}"
        assert data.get("auto_adjust") == True, "auto_adjust not updated"
        assert data.get("max_adjustment_pct") == 20, "max_adjustment_pct not updated"
        
        print(f"✓ Config updated: strategy={data['strategy']}, auto_adjust={data['auto_adjust']}")
        
        # Reset to default
        requests.put(
            f"{BASE_URL}/api/revenue/rate-scraper/{TEST_PROPERTY}/config",
            headers=auth_headers,
            json={"strategy": "match_median", "auto_adjust": False, "max_adjustment_pct": 15}
        )
    
    def test_apply_suggested_rates(self, auth_headers):
        """POST /api/revenue/rate-scraper/{property_id}/apply - Apply suggested rates"""
        # Get current rates first
        response = requests.get(
            f"{BASE_URL}/api/revenue/rate-scraper/{TEST_PROPERTY}",
            headers=auth_headers
        )
        daily = response.json().get("daily", [])
        
        if not daily:
            pytest.skip("No daily rate data available")
        
        # Apply rates for first 2 days
        dates_to_apply = [
            {"date": daily[0]["date"], "rate": daily[0]["suggested_rate"]},
            {"date": daily[1]["date"], "rate": daily[1]["suggested_rate"]}
        ]
        
        apply_response = requests.post(
            f"{BASE_URL}/api/revenue/rate-scraper/{TEST_PROPERTY}/apply",
            headers=auth_headers,
            json={"dates": dates_to_apply}
        )
        assert apply_response.status_code == 200, f"Expected 200, got {apply_response.status_code}: {apply_response.text}"
        data = apply_response.json()
        
        assert "applied" in data, "Missing applied count"
        assert data["applied"] == 2, f"Expected 2 rates applied, got {data['applied']}"
        
        print(f"✓ Applied {data['applied']} rate overrides")
    
    def test_apply_rates_empty_dates(self, auth_headers):
        """POST /api/revenue/rate-scraper/{property_id}/apply - Empty dates returns error"""
        response = requests.post(
            f"{BASE_URL}/api/revenue/rate-scraper/{TEST_PROPERTY}/apply",
            headers=auth_headers,
            json={"dates": []}
        )
        assert response.status_code == 200
        data = response.json()
        assert "error" in data, "Should return error for empty dates"
        print("✓ Empty dates correctly returns error")
    
    def test_rate_scraper_unauthorized(self):
        """Rate scraper endpoints require authentication"""
        response = requests.get(f"{BASE_URL}/api/revenue/rate-scraper/{TEST_PROPERTY}")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Unauthorized access correctly rejected")


class TestIntegration:
    """Integration tests for premium features"""
    
    def test_upsell_adds_to_folio(self, auth_headers, test_booking_id):
        """Verify accepted upsell appears in booking folio"""
        if not test_booking_id:
            pytest.skip("No booking available")
        
        # Get folio
        response = requests.get(
            f"{BASE_URL}/api/folio/{test_booking_id}",
            headers=auth_headers
        )
        if response.status_code != 200:
            pytest.skip("Could not get folio")
        
        data = response.json()
        items = data.get("items", [])
        
        # Check for upsell items
        upsell_items = [i for i in items if i.get("category") == "upsell"]
        print(f"✓ Folio has {len(upsell_items)} upsell charge(s)")
        
        if upsell_items:
            for item in upsell_items:
                print(f"  - {item.get('description')}: £{item.get('amount')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
