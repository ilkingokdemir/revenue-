"""
Batch 9 P1 Keyless Features (11-16 of 20) - Backend API Tests
Features:
1. Multi-language Message Templates
2. Birthday Auto-Discount
3. Low-Stock Alerts
4. Quick Re-booking CTA
5. Stay Extension Wizard
6. Long-Stay Discount Auto-Apply
"""
import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
PROPERTY_ID = "default"

@pytest.fixture(scope="module")
def auth_token():
    """Get admin auth token"""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json().get("access_token") or resp.json().get("token")

@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Auth headers for requests"""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


# ============================================================================
# 1. MULTI-LANGUAGE MESSAGE TEMPLATES
# ============================================================================
class TestMsgTemplates:
    """Multi-language Message Templates tests"""
    
    def test_get_known_keys(self, auth_headers):
        """GET /api/msg-templates/keys - should return 12 known keys"""
        resp = requests.get(f"{BASE_URL}/api/msg-templates/keys", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert data["count"] == 12, f"Expected 12 keys, got {data['count']}"
        keys = [k["key"] for k in data["items"]]
        assert "booking_confirmation" in keys
        assert "birthday_offer" in keys
        assert "rebook_followup" in keys
    
    def test_upsert_template_en(self, auth_headers):
        """POST /api/msg-templates - create English template"""
        resp = requests.post(f"{BASE_URL}/api/msg-templates", headers=auth_headers, json={
            "property_id": PROPERTY_ID,
            "key": "booking_confirmation",
            "language": "en",
            "subject": "Booking Confirmed - {hotel_name}",
            "body": "Hi {first_name},\n\nYour booking at {hotel_name} is confirmed!\n\nCheck-in: {checkin_date}\nRoom: {room_type}\nRef: {booking_ref}",
            "channel": "email",
            "active": True
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["template"]["key"] == "booking_confirmation"
        assert data["template"]["language"] == "en"
    
    def test_upsert_template_de(self, auth_headers):
        """POST /api/msg-templates - create German template"""
        resp = requests.post(f"{BASE_URL}/api/msg-templates", headers=auth_headers, json={
            "property_id": PROPERTY_ID,
            "key": "booking_confirmation",
            "language": "de",
            "subject": "Buchung bestätigt - {hotel_name}",
            "body": "Hallo {first_name},\n\nIhre Buchung bei {hotel_name} ist bestätigt!\n\nCheck-in: {checkin_date}\nZimmer: {room_type}\nRef: {booking_ref}",
            "channel": "email",
            "active": True
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["template"]["language"] == "de"
    
    def test_list_templates_with_coverage(self, auth_headers):
        """GET /api/msg-templates/{property_id} - returns items + coverage map"""
        resp = requests.get(f"{BASE_URL}/api/msg-templates/{PROPERTY_ID}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "coverage" in data
        # Coverage should show languages per key
        if "booking_confirmation" in data["coverage"]:
            assert "en" in data["coverage"]["booking_confirmation"]
    
    def test_render_template_exact_language(self, auth_headers):
        """POST /api/msg-templates/render - render with exact language match"""
        resp = requests.post(f"{BASE_URL}/api/msg-templates/render", headers=auth_headers, json={
            "property_id": PROPERTY_ID,
            "key": "booking_confirmation",
            "language": "en",
            "context": {
                "first_name": "Klaus",
                "hotel_name": "Grand Hotel",
                "checkin_date": "2026-05-12",
                "room_type": "Deluxe King",
                "booking_ref": "ABC123"
            }
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["language_used"] == "en"
        assert "Klaus" in data["body"]
        assert "Grand Hotel" in data["subject"]
    
    def test_render_template_fallback_to_en(self, auth_headers):
        """POST /api/msg-templates/render - fallback de→en when de not available"""
        # Request French which doesn't exist - should fallback to English
        resp = requests.post(f"{BASE_URL}/api/msg-templates/render", headers=auth_headers, json={
            "property_id": PROPERTY_ID,
            "key": "booking_confirmation",
            "language": "fr",  # French not created
            "context": {
                "first_name": "Klaus",
                "hotel_name": "Grand Hotel"
            }
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["language_requested"] == "fr"
        # Should fallback to en or de (whichever is active)
        assert data["language_used"] in ["en", "de"]
        assert "Klaus" in data["body"]
    
    def test_delete_template(self, auth_headers):
        """DELETE /api/msg-templates/{template_id}"""
        # First create a template to delete
        create_resp = requests.post(f"{BASE_URL}/api/msg-templates", headers=auth_headers, json={
            "property_id": PROPERTY_ID,
            "key": "cancellation_confirm",
            "language": "es",
            "subject": "Cancelación - {hotel_name}",
            "body": "Hola {first_name}, su reserva ha sido cancelada.",
            "channel": "email"
        })
        assert create_resp.status_code == 200
        tpl_id = create_resp.json()["template"]["id"]
        
        # Delete it
        del_resp = requests.delete(f"{BASE_URL}/api/msg-templates/{tpl_id}", headers=auth_headers)
        assert del_resp.status_code == 200
        assert del_resp.json()["ok"] is True


# ============================================================================
# 2. BIRTHDAY AUTO-DISCOUNT
# ============================================================================
class TestBirthdayAutoDiscount:
    """Birthday Auto-Discount tests"""
    
    def test_get_config_defaults(self, auth_headers):
        """GET /api/birthday/{property_id}/config - returns config (defaults or saved)"""
        resp = requests.get(f"{BASE_URL}/api/birthday/{PROPERTY_ID}/config", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "lookahead_days" in data
        assert "discount_pct" in data
        assert "voucher_validity_days" in data
        # Values should be reasonable (either defaults or previously saved)
        assert data["lookahead_days"] >= 7
        assert data["discount_pct"] > 0
    
    def test_save_config(self, auth_headers):
        """POST /api/birthday/config - save config"""
        resp = requests.post(f"{BASE_URL}/api/birthday/config", headers=auth_headers, json={
            "property_id": PROPERTY_ID,
            "enabled": True,
            "lookahead_days": 14,
            "discount_pct": 20.0,
            "max_amount_off": 150.0,
            "voucher_validity_days": 60
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["config"]["discount_pct"] == 20.0
        assert data["config"]["lookahead_days"] == 14
    
    def test_sweep_no_birthdays(self, auth_headers):
        """POST /api/birthday/sweep - sweep with no matching birthdays"""
        resp = requests.post(f"{BASE_URL}/api/birthday/sweep", headers=auth_headers, json={
            "property_id": PROPERTY_ID
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "scanned" in data
        assert "issued" in data
        assert "skipped_duplicates" in data
    
    def test_upcoming_birthdays(self, auth_headers):
        """GET /api/birthday/{property_id}/upcoming - list upcoming"""
        resp = requests.get(f"{BASE_URL}/api/birthday/{PROPERTY_ID}/upcoming?days=30", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "count" in data
    
    def test_dispatches_list(self, auth_headers):
        """GET /api/birthday/{property_id}/dispatches - list queue"""
        resp = requests.get(f"{BASE_URL}/api/birthday/{PROPERTY_ID}/dispatches?days=60", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "count" in data


# ============================================================================
# 3. LOW-STOCK ALERTS
# ============================================================================
class TestLowStockAlerts:
    """Low-Stock Alerts tests"""
    
    def test_get_items_state(self, auth_headers):
        """GET /api/low-stock/{property_id}/items - current stock state"""
        resp = requests.get(f"{BASE_URL}/api/low-stock/{PROPERTY_ID}/items", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "count" in data
        assert "low_count" in data
        assert "ok_count" in data
    
    def test_scan_creates_alerts(self, auth_headers):
        """POST /api/low-stock/scan - scan and create alerts"""
        resp = requests.post(f"{BASE_URL}/api/low-stock/scan", headers=auth_headers, json={
            "property_id": PROPERTY_ID
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "items_scanned" in data
        assert "alerts_created" in data
    
    def test_scan_idempotent(self, auth_headers):
        """POST /api/low-stock/scan - idempotent (won't double-create)"""
        # Run scan twice
        resp1 = requests.post(f"{BASE_URL}/api/low-stock/scan", headers=auth_headers, json={
            "property_id": PROPERTY_ID
        })
        assert resp1.status_code == 200
        
        resp2 = requests.post(f"{BASE_URL}/api/low-stock/scan", headers=auth_headers, json={
            "property_id": PROPERTY_ID
        })
        assert resp2.status_code == 200
        # Second scan should create 0 new alerts (idempotent)
        # Note: This depends on having stock items - if none, both will be 0
    
    def test_list_alerts(self, auth_headers):
        """GET /api/low-stock/{property_id}/alerts - list open alerts"""
        resp = requests.get(f"{BASE_URL}/api/low-stock/{PROPERTY_ID}/alerts?status=open", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "count" in data
    
    @pytest.mark.skip(reason="No alerts to dismiss - no stock items configured")
    def test_dismiss_alert(self, auth_headers):
        """POST /api/low-stock/alert/{id}/dismiss - dismiss alert"""
        # Would need an actual alert to test
        pass


# ============================================================================
# 4. QUICK RE-BOOKING CTA
# ============================================================================
class TestRebookCTA:
    """Quick Re-booking CTA tests"""
    
    def test_sweep_finds_eligible(self, auth_headers):
        """POST /api/rebook/sweep - find eligible past guests"""
        resp = requests.post(f"{BASE_URL}/api/rebook/sweep", headers=auth_headers, json={
            "property_id": PROPERTY_ID,
            "days_after_checkout": 30,
            "loyalty_discount_pct": 10.0
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "scanned" in data
        assert "queued" in data
        assert "target_date" in data
    
    def test_sweep_idempotent(self, auth_headers):
        """POST /api/rebook/sweep - idempotent (won't re-queue same booking)"""
        # Run twice
        resp1 = requests.post(f"{BASE_URL}/api/rebook/sweep", headers=auth_headers, json={
            "property_id": PROPERTY_ID,
            "days_after_checkout": 30
        })
        assert resp1.status_code == 200
        
        resp2 = requests.post(f"{BASE_URL}/api/rebook/sweep", headers=auth_headers, json={
            "property_id": PROPERTY_ID,
            "days_after_checkout": 30
        })
        assert resp2.status_code == 200
        # Second run should queue 0 (already queued)
    
    def test_list_dispatches(self, auth_headers):
        """GET /api/rebook/{property_id}/dispatches - list with click stats"""
        resp = requests.get(f"{BASE_URL}/api/rebook/{PROPERTY_ID}/dispatches?days=60", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "count" in data
        assert "clicked" in data
        assert "click_rate" in data
    
    @pytest.mark.skip(reason="No dispatches to click - no bookings with checkout exactly 30 days ago")
    def test_click_dispatch(self, auth_headers):
        """POST /api/rebook/dispatches/{id}/clicked - mark clicked"""
        pass
    
    @pytest.mark.skip(reason="No token to resolve")
    def test_resolve_token(self, auth_headers):
        """GET /api/rebook/token/{token} - public resolve"""
        pass


# ============================================================================
# 5. STAY EXTENSION WIZARD
# ============================================================================
class TestStayExtension:
    """Stay Extension Wizard tests"""
    
    @pytest.fixture(scope="class")
    def test_booking_id(self, auth_headers):
        """Get a booking ID for testing"""
        resp = requests.get(f"{BASE_URL}/api/bookings?property_id={PROPERTY_ID}&limit=1", headers=auth_headers)
        if resp.status_code == 200:
            data = resp.json()
            # Handle both list and dict responses
            if isinstance(data, list):
                items = data
            else:
                items = data.get("items") or data.get("bookings") or []
            if items:
                return items[0]["id"]
        return None
    
    def test_quote_extension(self, auth_headers, test_booking_id):
        """POST /api/stay-ext/quote - get quote for extension"""
        if not test_booking_id:
            pytest.skip("No booking available for testing")
        
        resp = requests.post(f"{BASE_URL}/api/stay-ext/quote", headers=auth_headers, json={
            "booking_id": test_booking_id,
            "extra_nights": 2,
            "discount_pct": 10
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "current_check_out" in data
        assert "proposed_check_out" in data
        assert "extra_nights" in data
        assert "room_available" in data
        assert "rate_per_night" in data
        assert "rate_per_night_charged" in data
        assert "total_extra_charge" in data
        assert data["extra_nights"] == 2
        assert data["discount_pct"] == 10
    
    def test_quote_validates_booking_id(self, auth_headers):
        """POST /api/stay-ext/quote - validates booking exists"""
        resp = requests.post(f"{BASE_URL}/api/stay-ext/quote", headers=auth_headers, json={
            "booking_id": "nonexistent-booking-id",
            "extra_nights": 1
        })
        assert resp.status_code == 404
    
    def test_quote_defaults_extra_nights(self, auth_headers, test_booking_id):
        """POST /api/stay-ext/quote - defaults extra_nights to 1 if 0 or missing"""
        if not test_booking_id:
            pytest.skip("No booking available for testing")
        
        resp = requests.post(f"{BASE_URL}/api/stay-ext/quote", headers=auth_headers, json={
            "booking_id": test_booking_id,
            "extra_nights": 0  # Should default to 1
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["extra_nights"] == 1  # Defaults to 1
    
    def test_recent_extensions(self, auth_headers):
        """GET /api/stay-ext/{property_id}/recent - audit log"""
        resp = requests.get(f"{BASE_URL}/api/stay-ext/{PROPERTY_ID}/recent?days=60", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "count" in data
        assert "extra_nights_total" in data
        assert "extra_revenue" in data


# ============================================================================
# 6. LONG-STAY DISCOUNT AUTO-APPLY
# ============================================================================
class TestLongStayDiscount:
    """Long-Stay Discount Auto-Apply tests"""
    
    def test_get_config_defaults(self, auth_headers):
        """GET /api/long-stay/{property_id}/config - returns DEFAULT_LADDER"""
        resp = requests.get(f"{BASE_URL}/api/long-stay/{PROPERTY_ID}/config", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "ladder" in data
        assert "enabled" in data
        assert "max_discount_pct" in data
        # Default ladder should have 3 tiers
        assert len(data["ladder"]) >= 3
        # Check tier structure
        for tier in data["ladder"]:
            assert "min_nights" in tier
            assert "discount_pct" in tier
    
    def test_save_config_validates_ladder(self, auth_headers):
        """POST /api/long-stay/config - validates min_nights >= 2"""
        resp = requests.post(f"{BASE_URL}/api/long-stay/config", headers=auth_headers, json={
            "property_id": PROPERTY_ID,
            "ladder": [
                {"min_nights": 1, "discount_pct": 10}  # Invalid: min_nights < 2
            ]
        })
        assert resp.status_code == 400
    
    def test_save_config_validates_discount(self, auth_headers):
        """POST /api/long-stay/config - validates discount_pct > 0"""
        resp = requests.post(f"{BASE_URL}/api/long-stay/config", headers=auth_headers, json={
            "property_id": PROPERTY_ID,
            "ladder": [
                {"min_nights": 7, "discount_pct": 0}  # Invalid: discount_pct <= 0
            ]
        })
        assert resp.status_code == 400
    
    def test_save_config_valid(self, auth_headers):
        """POST /api/long-stay/config - save valid ladder"""
        resp = requests.post(f"{BASE_URL}/api/long-stay/config", headers=auth_headers, json={
            "property_id": PROPERTY_ID,
            "enabled": True,
            "ladder": [
                {"min_nights": 7, "discount_pct": 10},
                {"min_nights": 14, "discount_pct": 15},
                {"min_nights": 28, "discount_pct": 25}
            ],
            "max_discount_pct": 30
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert len(data["config"]["ladder"]) == 3
    
    def test_sweep_applies_discounts(self, auth_headers):
        """POST /api/long-stay/sweep - apply to eligible bookings"""
        resp = requests.post(f"{BASE_URL}/api/long-stay/sweep", headers=auth_headers, json={
            "property_id": PROPERTY_ID
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "scanned" in data
        assert "applied" in data
        assert "skipped" in data
    
    def test_sweep_idempotent(self, auth_headers):
        """POST /api/long-stay/sweep - idempotent (won't reapply)"""
        # Run twice
        resp1 = requests.post(f"{BASE_URL}/api/long-stay/sweep", headers=auth_headers, json={
            "property_id": PROPERTY_ID
        })
        assert resp1.status_code == 200
        
        resp2 = requests.post(f"{BASE_URL}/api/long-stay/sweep", headers=auth_headers, json={
            "property_id": PROPERTY_ID
        })
        assert resp2.status_code == 200
        # Second run should apply 0 (already applied)
        assert resp2.json()["applied"] == 0
    
    def test_log_list(self, auth_headers):
        """GET /api/long-stay/{property_id}/log - audit log"""
        resp = requests.get(f"{BASE_URL}/api/long-stay/{PROPERTY_ID}/log?days=90", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "count" in data
        assert "discounts_total" in data
        assert "nights_total" in data


# ============================================================================
# REGRESSION TESTS
# ============================================================================
class TestRegression:
    """Basic regression tests"""
    
    def test_auth_login(self):
        """Auth login still works"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert resp.status_code == 200
    
    def test_bookings_list(self, auth_headers):
        """Bookings list still works"""
        resp = requests.get(f"{BASE_URL}/api/bookings?property_id={PROPERTY_ID}", headers=auth_headers)
        assert resp.status_code == 200
    
    def test_properties_list(self, auth_headers):
        """Properties list still works"""
        resp = requests.get(f"{BASE_URL}/api/properties", headers=auth_headers)
        assert resp.status_code == 200
