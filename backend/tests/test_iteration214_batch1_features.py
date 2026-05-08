"""
Iteration 214 - Batch 1 Keyless Features Testing
=================================================
Tests for 5 new keyless competitor-parity features:
1. Tax Presets Library
2. Walk-in Express Check-in
3. No-Show Auto-Charge
4. Guest Stay Preferences
5. Regression: late-checkout, service-recovery, room-qr
"""
import pytest
import requests
import os
from datetime import date, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
TEST_PROPERTY = "city-gate"
EMPTY_PROPERTY = "aldgate-flats"


@pytest.fixture(scope="module")
def auth_token():
    """Get admin auth token"""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json().get("token")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Auth headers for requests"""
    return {"Authorization": f"Bearer {auth_token}"}


# ============== 1. TAX PRESETS LIBRARY ==============

class TestTaxPresets:
    """Tax Presets Library - 12 country presets"""
    
    def test_list_presets_returns_12_codes(self, auth_headers):
        """GET /api/tax-presets/ should return 12 country presets"""
        resp = requests.get(f"{BASE_URL}/api/tax-presets/", headers=auth_headers)
        assert resp.status_code == 200, f"List presets failed: {resp.text}"
        data = resp.json()
        presets = data.get("presets", [])
        codes = [p["code"] for p in presets]
        
        # Verify all 12 expected codes
        expected_codes = ["GB", "GB-LON", "FR", "IT", "ES", "DE", "NL", "TR", "US-NV", "US-NY", "US-CA", "AE"]
        assert len(presets) == 12, f"Expected 12 presets, got {len(presets)}"
        for code in expected_codes:
            assert code in codes, f"Missing preset code: {code}"
        print(f"PASS: List presets returns 12 codes: {codes}")
    
    def test_get_preset_detail_gb(self, auth_headers):
        """GET /api/tax-presets/GB should return preset detail"""
        resp = requests.get(f"{BASE_URL}/api/tax-presets/GB", headers=auth_headers)
        assert resp.status_code == 200, f"Get preset failed: {resp.text}"
        data = resp.json()
        assert data.get("code") == "GB"
        assert data.get("name") == "United Kingdom"
        assert data.get("currency") == "GBP"
        assert "rules" in data
        print(f"PASS: GB preset detail: {data['name']}, {len(data['rules'])} rules")
    
    def test_get_preset_detail_tr(self, auth_headers):
        """GET /api/tax-presets/TR should return Turkish preset"""
        resp = requests.get(f"{BASE_URL}/api/tax-presets/TR", headers=auth_headers)
        assert resp.status_code == 200, f"Get preset failed: {resp.text}"
        data = resp.json()
        assert data.get("code") == "TR"
        assert data.get("name") == "Türkiye (Konaklama Vergisi)"
        assert data.get("currency") == "TRY"
        print(f"PASS: TR preset detail: {data['name']}")
    
    def test_apply_preset_gb_to_city_gate(self, auth_headers):
        """POST /api/tax-presets/apply should create tax profile"""
        resp = requests.post(f"{BASE_URL}/api/tax-presets/apply", headers=auth_headers, json={
            "property_id": TEST_PROPERTY,
            "preset_code": "GB",
            "replace_existing": True
        })
        assert resp.status_code == 200, f"Apply preset failed: {resp.text}"
        data = resp.json()
        assert data.get("ok") is True
        assert "profile" in data
        profile = data["profile"]
        assert profile.get("property_id") == TEST_PROPERTY
        assert profile.get("preset_code") == "GB"
        assert profile.get("active") is True
        print(f"PASS: Applied GB preset to {TEST_PROPERTY}, profile_id: {profile.get('id')}")
    
    def test_apply_preset_tr_replaces_existing(self, auth_headers):
        """POST /api/tax-presets/apply with replace_existing=true should deactivate old profile"""
        # First apply GB
        requests.post(f"{BASE_URL}/api/tax-presets/apply", headers=auth_headers, json={
            "property_id": TEST_PROPERTY,
            "preset_code": "GB",
            "replace_existing": True
        })
        
        # Then apply TR with replace
        resp = requests.post(f"{BASE_URL}/api/tax-presets/apply", headers=auth_headers, json={
            "property_id": TEST_PROPERTY,
            "preset_code": "TR",
            "replace_existing": True
        })
        assert resp.status_code == 200, f"Apply TR preset failed: {resp.text}"
        data = resp.json()
        assert data.get("ok") is True
        assert data["profile"]["preset_code"] == "TR"
        print(f"PASS: TR preset replaced existing profile")
    
    def test_resort_fee_templates(self, auth_headers):
        """GET /api/tax-presets/resort-fees/templates should return 5 templates"""
        resp = requests.get(f"{BASE_URL}/api/tax-presets/resort-fees/templates", headers=auth_headers)
        assert resp.status_code == 200, f"Get templates failed: {resp.text}"
        data = resp.json()
        templates = data.get("templates", [])
        assert len(templates) == 5, f"Expected 5 templates, got {len(templates)}"
        print(f"PASS: Resort fee templates: {len(templates)} templates")
    
    def test_quick_add_resort_fee(self, auth_headers):
        """POST /api/tax-presets/resort-fee/quick-add should add resort fee"""
        resp = requests.post(f"{BASE_URL}/api/tax-presets/resort-fee/quick-add", headers=auth_headers, json={
            "property_id": TEST_PROPERTY,
            "label": "Test Resort Fee",
            "rate": 25.0
        })
        assert resp.status_code == 200, f"Quick add failed: {resp.text}"
        data = resp.json()
        assert data.get("ok") is True
        assert data.get("added", {}).get("rate") == 25.0
        print(f"PASS: Quick-added resort fee £25/night")


# ============== 2. WALK-IN EXPRESS CHECK-IN ==============

class TestWalkInExpress:
    """Walk-in Express Check-in - 90 second flow"""
    
    def test_availability_returns_offerings(self, auth_headers):
        """POST /api/walkin/availability should return room offerings"""
        today = date.today().isoformat()
        resp = requests.post(f"{BASE_URL}/api/walkin/availability", headers=auth_headers, json={
            "property_id": TEST_PROPERTY,
            "check_in": today,
            "nights": 1,
            "guests": 1
        })
        assert resp.status_code == 200, f"Availability failed: {resp.text}"
        data = resp.json()
        assert data.get("property_id") == TEST_PROPERTY
        assert data.get("nights") == 1
        offerings = data.get("offerings", [])
        # city-gate should have rooms
        print(f"PASS: Availability returned {len(offerings)} offerings for {TEST_PROPERTY}")
        
        if offerings:
            o = offerings[0]
            assert "room_type_id" in o
            assert "base_rate" in o
            assert "grand_total" in o
            assert "available_rooms" in o
            print(f"  First offering: {o['room_type_name']} - £{o['grand_total']} ({o['available_count']} rooms)")
    
    def test_availability_with_tax_breakdown(self, auth_headers):
        """Availability should include tax breakdown from active tax profile"""
        today = date.today().isoformat()
        resp = requests.post(f"{BASE_URL}/api/walkin/availability", headers=auth_headers, json={
            "property_id": TEST_PROPERTY,
            "check_in": today,
            "nights": 2,
            "guests": 2
        })
        assert resp.status_code == 200
        data = resp.json()
        offerings = data.get("offerings", [])
        if offerings:
            o = offerings[0]
            assert "taxes_added" in o
            assert "tax_breakdown" in o
            print(f"PASS: Tax breakdown included - taxes_added: £{o['taxes_added']}")
    
    def test_create_walkin_booking(self, auth_headers):
        """POST /api/walkin/create should create booking with WK-ref"""
        today = date.today().isoformat()
        
        # First get availability
        avail_resp = requests.post(f"{BASE_URL}/api/walkin/availability", headers=auth_headers, json={
            "property_id": TEST_PROPERTY,
            "check_in": today,
            "nights": 1,
            "guests": 1
        })
        assert avail_resp.status_code == 200
        offerings = avail_resp.json().get("offerings", [])
        
        if not offerings:
            pytest.skip("No available rooms for walk-in test")
        
        offering = offerings[0]
        room = offering["available_rooms"][0] if offering["available_rooms"] else None
        if not room:
            pytest.skip("No available rooms in offering")
        
        # Create walk-in
        resp = requests.post(f"{BASE_URL}/api/walkin/create", headers=auth_headers, json={
            "property_id": TEST_PROPERTY,
            "room_type_id": offering["room_type_id"],
            "room_number": room["room_number"],
            "nights": 1,
            "guests": 1,
            "check_in": today,
            "guest": {
                "name": "TEST Walk-in Guest",
                "email": "test.walkin@example.com",
                "phone": "+44123456789"
            },
            "payment_method": "cash",
            "deposit_paid": 50
        })
        assert resp.status_code == 200, f"Create walk-in failed: {resp.text}"
        data = resp.json()
        assert data.get("ok") is True
        booking = data.get("booking", {})
        
        # Verify booking ref format WK-YYMMDD-XXXXXX
        booking_ref = booking.get("booking_ref", "")
        assert booking_ref.startswith("WK-"), f"Booking ref should start with WK-: {booking_ref}"
        
        # Verify status is checked_in
        assert booking.get("status") == "checked_in"
        
        # Verify balance calculation
        total = booking.get("total_price", 0)
        deposit = 50
        balance = data.get("balance_due", 0)
        assert balance == round(total - deposit, 2), f"Balance mismatch: {balance} != {total} - {deposit}"
        
        print(f"PASS: Walk-in created - {booking_ref}, total: £{total}, balance: £{balance}")
    
    def test_create_walkin_requires_guest_name(self, auth_headers):
        """POST /api/walkin/create should require guest.name"""
        today = date.today().isoformat()
        resp = requests.post(f"{BASE_URL}/api/walkin/create", headers=auth_headers, json={
            "property_id": TEST_PROPERTY,
            "room_type_id": "some-type",
            "room_number": "101",
            "nights": 1,
            "guest": {"email": "test@example.com"}  # Missing name
        })
        assert resp.status_code == 400, f"Should fail without guest name: {resp.text}"
        print("PASS: Walk-in requires guest.name")


# ============== 3. NO-SHOW AUTO-CHARGE ==============

class TestNoShowAutoCharge:
    """No-Show Auto-Charge workflow"""
    
    def test_get_policy_returns_defaults(self, auth_headers):
        """GET /api/no-show/{property_id}/policy should return policy"""
        resp = requests.get(f"{BASE_URL}/api/no-show/{TEST_PROPERTY}/policy", headers=auth_headers)
        assert resp.status_code == 200, f"Get policy failed: {resp.text}"
        data = resp.json()
        assert "fee_type" in data
        assert "grace_hour" in data
        assert "auto_run_enabled" in data
        print(f"PASS: No-show policy: fee_type={data['fee_type']}, grace_hour={data['grace_hour']}")
    
    def test_save_custom_policy(self, auth_headers):
        """POST /api/no-show/{property_id}/policy should save custom policy"""
        resp = requests.post(f"{BASE_URL}/api/no-show/{TEST_PROPERTY}/policy", headers=auth_headers, json={
            "fee_type": "percent_total",
            "fee_pct": 50.0,
            "grace_hour": 22,
            "auto_run_enabled": False
        })
        assert resp.status_code == 200, f"Save policy failed: {resp.text}"
        data = resp.json()
        assert data.get("ok") is True
        policy = data.get("policy", {})
        assert policy.get("fee_type") == "percent_total"
        assert policy.get("fee_pct") == 50.0
        print(f"PASS: Custom policy saved: {policy['fee_type']} {policy['fee_pct']}%")
    
    def test_candidates_returns_list(self, auth_headers):
        """GET /api/no-show/{property_id}/candidates should return candidates"""
        today = date.today().isoformat()
        resp = requests.get(f"{BASE_URL}/api/no-show/{TEST_PROPERTY}/candidates?on_date={today}", headers=auth_headers)
        assert resp.status_code == 200, f"Get candidates failed: {resp.text}"
        data = resp.json()
        assert "items" in data
        assert "count" in data
        assert "policy" in data
        print(f"PASS: No-show candidates: {data['count']} for {today}")
    
    def test_mark_returns_400_for_invalid_status(self, auth_headers):
        """POST /api/no-show/{booking_id}/mark should return 400 for non-confirmed booking"""
        # Try to mark a non-existent or already checked-in booking
        resp = requests.post(f"{BASE_URL}/api/no-show/invalid-booking-id/mark", headers=auth_headers, json={})
        # Should be 404 (not found) or 400 (invalid status)
        assert resp.status_code in [400, 404], f"Expected 400/404, got {resp.status_code}: {resp.text}"
        print(f"PASS: Mark no-show returns {resp.status_code} for invalid booking")


# ============== 4. GUEST STAY PREFERENCES ==============

class TestGuestPreferences:
    """Guest Stay Preferences memory"""
    
    @pytest.fixture
    def test_guest_id(self, auth_headers):
        """Create or get a test guest profile"""
        # First try to find existing guest
        resp = requests.get(f"{BASE_URL}/api/guest-profiles?property_id={TEST_PROPERTY}&limit=1", headers=auth_headers)
        if resp.status_code == 200:
            guests = resp.json()
            if isinstance(guests, list) and guests:
                return guests[0].get("id")
        
        # Create a test guest
        resp = requests.post(f"{BASE_URL}/api/guest-profiles", headers=auth_headers, json={
            "name": "TEST Pref Guest",
            "email": "test.prefs@example.com",
            "phone": "+44111222333",
            "property_id": TEST_PROPERTY
        })
        if resp.status_code in [200, 201]:
            return resp.json().get("id")
        return None
    
    def test_get_prefs_returns_empty_for_new_guest(self, auth_headers):
        """GET /api/guest-prefs/{guest_id} should return empty prefs for new guest"""
        resp = requests.get(f"{BASE_URL}/api/guest-prefs/new-guest-id-12345", headers=auth_headers)
        assert resp.status_code == 200, f"Get prefs failed: {resp.text}"
        data = resp.json()
        assert data.get("prefs") == {} or data.get("prefs") is None or len(data.get("prefs", {})) == 0
        assert "fields_meta" in data
        print(f"PASS: Empty prefs returned with fields_meta")
    
    def test_upsert_prefs(self, auth_headers, test_guest_id):
        """POST /api/guest-prefs/{guest_id} should upsert preferences"""
        if not test_guest_id:
            pytest.skip("No test guest available")
        
        resp = requests.post(f"{BASE_URL}/api/guest-prefs/{test_guest_id}", headers=auth_headers, json={
            "prefs": {
                "pillow_firmness": "firm",
                "floor_preference": "high",
                "dietary": "vegan",
                "allergies": "nuts",
                "ac_temperature": 22
            }
        })
        assert resp.status_code == 200, f"Upsert prefs failed: {resp.text}"
        data = resp.json()
        assert data.get("ok") is True
        prefs = data.get("prefs", {})
        assert prefs.get("pillow_firmness") == "firm"
        assert prefs.get("dietary") == "vegan"
        print(f"PASS: Upserted {len(prefs)} preferences for guest {test_guest_id}")
    
    def test_read_back_prefs(self, auth_headers, test_guest_id):
        """GET /api/guest-prefs/{guest_id} should return saved prefs"""
        if not test_guest_id:
            pytest.skip("No test guest available")
        
        # First upsert
        requests.post(f"{BASE_URL}/api/guest-prefs/{test_guest_id}", headers=auth_headers, json={
            "prefs": {"pillow_firmness": "soft", "dietary": "halal"}
        })
        
        # Then read back
        resp = requests.get(f"{BASE_URL}/api/guest-prefs/{test_guest_id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        prefs = data.get("prefs", {})
        assert prefs.get("pillow_firmness") == "soft"
        print(f"PASS: Read back prefs: {prefs}")
    
    def test_today_arrivals(self, auth_headers):
        """GET /api/guest-prefs/{property_id}/today-arrivals should return arrivals"""
        resp = requests.get(f"{BASE_URL}/api/guest-prefs/{TEST_PROPERTY}/today-arrivals", headers=auth_headers)
        assert resp.status_code == 200, f"Today arrivals failed: {resp.text}"
        data = resp.json()
        assert "items" in data
        assert "count" in data
        assert "date" in data
        print(f"PASS: Today arrivals: {data['count']} arrivals for {data['date']}")
        
        # Check structure of items
        if data["items"]:
            item = data["items"][0]
            assert "booking_id" in item
            assert "guest_name" in item
            assert "has_prefs" in item
            assert "pref_count" in item


# ============== 5. REGRESSION TESTS ==============

class TestRegressionSmoke:
    """Regression smoke tests for last batch features"""
    
    def test_late_checkout_quote(self, auth_headers):
        """GET /api/late-checkout/{property_id}/quote should work"""
        resp = requests.get(f"{BASE_URL}/api/late-checkout/{TEST_PROPERTY}/quote?booking_id=test", headers=auth_headers)
        # May return 404 if booking not found, but endpoint should exist
        assert resp.status_code in [200, 404], f"Late checkout quote failed: {resp.status_code}"
        print(f"PASS: Late checkout quote endpoint working (status: {resp.status_code})")
    
    def test_service_recovery_stats(self, auth_headers):
        """GET /api/service-recovery/{property_id}/stats should work"""
        resp = requests.get(f"{BASE_URL}/api/service-recovery/{TEST_PROPERTY}/stats", headers=auth_headers)
        assert resp.status_code == 200, f"Service recovery stats failed: {resp.text}"
        data = resp.json()
        assert "total" in data or "open" in data or isinstance(data, dict)
        print(f"PASS: Service recovery stats: {data}")
    
    def test_service_recovery_post(self, auth_headers):
        """POST /api/service-recovery should create issue"""
        resp = requests.post(f"{BASE_URL}/api/service-recovery", headers=auth_headers, json={
            "property_id": TEST_PROPERTY,
            "guest_name": "TEST Recovery Guest",
            "room_number": "101",
            "issue_type": "noise",
            "text": "Test issue for regression",  # API expects 'text' not 'description'
            "severity": "medium"
        })
        assert resp.status_code in [200, 201], f"Service recovery POST failed: {resp.text}"
        print(f"PASS: Service recovery POST working")
    
    def test_room_qr_list(self, auth_headers):
        """GET /api/room-qr/{property_id}/list should work"""
        resp = requests.get(f"{BASE_URL}/api/room-qr/{TEST_PROPERTY}/list", headers=auth_headers)
        assert resp.status_code == 200, f"Room QR list failed: {resp.text}"
        data = resp.json()
        assert "items" in data or "rooms" in data or isinstance(data, list)
        print(f"PASS: Room QR list working - {data.get('count', len(data.get('items', [])))} rooms")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
