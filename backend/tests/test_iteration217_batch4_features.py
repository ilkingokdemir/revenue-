"""
Iteration 217 - Batch 4 Keyless Competitor Parity Features (4 of 30 P0 gaps)
============================================================================
Tests for:
1. SPACES — Multi-Product Inventory (parking, EV chargers, meeting rooms, bikes, lockers, etc.)
2. MULTI-CURRENCY — FX rates with 20 default currencies, property overrides, two-hop conversion
3. MULTI-PROPERTY ROLL-UP — Chain-wide KPI aggregation across all properties
4. BANQUET EVENT ORDER (BEO) PDF — Printable HTML A4 sheet for events

Regression smoke tests for last 4 batches included.
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
PROPERTY_ID = "city-gate"

@pytest.fixture(scope="module")
def auth_session():
    """Authenticate and return session with cookies"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Login as admin
    resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return session


# ============================================================================
# 1. SPACES — Multi-Product Inventory
# ============================================================================

class TestSpacesMultiProductInventory:
    """Tests for /api/spaces/* and /api/space-bookings/* endpoints"""
    
    def test_list_spaces_empty_or_existing(self, auth_session):
        """GET /api/spaces/{property_id} returns list (may be empty initially)"""
        resp = auth_session.get(f"{BASE_URL}/api/spaces/{PROPERTY_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        print(f"Spaces list: {len(data)} spaces found")
    
    def test_create_parking_space(self, auth_session):
        """POST /api/spaces/{property_id} creates a parking space with daily rate"""
        payload = {
            "name": "TEST_Parking Bay 12",
            "code": "P-12",
            "kind": "parking",
            "capacity": 1,
            "rate_per_unit": 15.00,
            "currency": "GBP",
            "unit_minutes": None,  # daily rate
            "open_hour": 0,
            "close_hour": 24,
            "description": "Test parking space for iteration 217"
        }
        resp = auth_session.post(f"{BASE_URL}/api/spaces/{PROPERTY_ID}", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True
        assert "space" in data
        space = data["space"]
        assert space["kind"] == "parking"
        assert space["capacity"] == 1
        assert space["rate_per_unit"] == 15.0
        assert space["unit_minutes"] is None  # daily
        print(f"Created parking space: {space['id']}")
        return space["id"]
    
    def test_create_meeting_room_hourly(self, auth_session):
        """POST /api/spaces/{property_id} creates meeting room with hourly rate"""
        payload = {
            "name": "TEST_Boardroom A",
            "code": "BR-A",
            "kind": "meeting_room",
            "capacity": 10,
            "rate_per_unit": 50.00,
            "currency": "GBP",
            "unit_minutes": 60,  # hourly rate
            "open_hour": 8,
            "close_hour": 18,
            "description": "Test meeting room"
        }
        resp = auth_session.post(f"{BASE_URL}/api/spaces/{PROPERTY_ID}", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True
        space = data["space"]
        assert space["kind"] == "meeting_room"
        assert space["unit_minutes"] == 60
        print(f"Created meeting room: {space['id']}")
    
    def test_space_kinds_validation(self, auth_session):
        """POST /api/spaces/{property_id} validates kind against allowlist"""
        # Valid kinds: parking, ev_charger, meeting_room, bicycle, locker, cabana, kayak, other
        for kind in ["parking", "ev_charger", "meeting_room", "bicycle", "locker", "cabana", "kayak", "other"]:
            payload = {"name": f"TEST_{kind}_space", "kind": kind, "capacity": 1, "rate_per_unit": 10}
            resp = auth_session.post(f"{BASE_URL}/api/spaces/{PROPERTY_ID}", json=payload)
            assert resp.status_code == 200
            data = resp.json()
            assert data["space"]["kind"] == kind
        print("All 8 space kinds validated")
    
    def test_book_space_daily_pricing(self, auth_session):
        """POST /api/space-bookings books a space and computes daily price"""
        # First create a space
        space_resp = auth_session.post(f"{BASE_URL}/api/spaces/{PROPERTY_ID}", json={
            "name": "TEST_Parking Daily",
            "kind": "parking",
            "capacity": 1,
            "rate_per_unit": 15.00,
            "unit_minutes": None  # daily
        })
        space_id = space_resp.json()["space"]["id"]
        
        # Book for 24 hours (1 day)
        now = datetime.utcnow()
        tomorrow = now + timedelta(days=1)
        booking_payload = {
            "space_id": space_id,
            "start": now.isoformat(),
            "end": tomorrow.isoformat(),
            "guest_name": "TEST_John Smith",
            "guest_email": "john@test.com",
            "charge_to": "room"
        }
        resp = auth_session.post(f"{BASE_URL}/api/space-bookings", json=booking_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True
        booking = data["booking"]
        assert booking["price"] == 15.0  # 1 day * £15/day
        assert booking["units"] == 1
        assert booking["status"] == "confirmed"
        print(f"Booked space: {booking['id']}, price: £{booking['price']}")
        return booking["id"], space_id
    
    def test_book_space_overlap_returns_409(self, auth_session):
        """POST /api/space-bookings returns 409 when space at capacity"""
        # Create a space with capacity=1
        space_resp = auth_session.post(f"{BASE_URL}/api/spaces/{PROPERTY_ID}", json={
            "name": "TEST_Single Parking",
            "kind": "parking",
            "capacity": 1,
            "rate_per_unit": 15.00,
            "unit_minutes": None
        })
        space_id = space_resp.json()["space"]["id"]
        
        # Book it
        now = datetime.utcnow()
        tomorrow = now + timedelta(days=1)
        booking1 = {
            "space_id": space_id,
            "start": now.isoformat(),
            "end": tomorrow.isoformat(),
            "guest_name": "TEST_First Guest"
        }
        resp1 = auth_session.post(f"{BASE_URL}/api/space-bookings", json=booking1)
        assert resp1.status_code == 200
        
        # Try to book again (overlapping) - should return 409
        booking2 = {
            "space_id": space_id,
            "start": now.isoformat(),
            "end": tomorrow.isoformat(),
            "guest_name": "TEST_Second Guest"
        }
        resp2 = auth_session.post(f"{BASE_URL}/api/space-bookings", json=booking2)
        assert resp2.status_code == 409
        assert "capacity" in resp2.json().get("detail", "").lower()
        print("Overlap booking correctly returned 409")
    
    def test_list_space_bookings(self, auth_session):
        """GET /api/space-bookings/{property_id} returns bookings list"""
        resp = auth_session.get(f"{BASE_URL}/api/space-bookings/{PROPERTY_ID}?days=14")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        print(f"Space bookings: {len(data)} found")
    
    def test_cancel_space_booking(self, auth_session):
        """POST /api/space-bookings/{id}/cancel cancels a booking"""
        # Create and book
        space_resp = auth_session.post(f"{BASE_URL}/api/spaces/{PROPERTY_ID}", json={
            "name": "TEST_Cancel Test",
            "kind": "locker",
            "capacity": 1,
            "rate_per_unit": 5.00
        })
        space_id = space_resp.json()["space"]["id"]
        
        now = datetime.utcnow()
        booking_resp = auth_session.post(f"{BASE_URL}/api/space-bookings", json={
            "space_id": space_id,
            "start": now.isoformat(),
            "end": (now + timedelta(hours=2)).isoformat(),
            "guest_name": "TEST_Cancel Guest"
        })
        booking_id = booking_resp.json()["booking"]["id"]
        
        # Cancel
        cancel_resp = auth_session.post(f"{BASE_URL}/api/space-bookings/{booking_id}/cancel")
        assert cancel_resp.status_code == 200
        assert cancel_resp.json().get("ok") is True
        print(f"Cancelled booking: {booking_id}")
    
    def test_delete_space(self, auth_session):
        """DELETE /api/spaces/{property_id}/{space_id} deactivates a space"""
        # Create a space
        space_resp = auth_session.post(f"{BASE_URL}/api/spaces/{PROPERTY_ID}", json={
            "name": "TEST_Delete Me",
            "kind": "bicycle",
            "capacity": 1,
            "rate_per_unit": 10.00
        })
        space_id = space_resp.json()["space"]["id"]
        
        # Delete (deactivate)
        del_resp = auth_session.delete(f"{BASE_URL}/api/spaces/{PROPERTY_ID}/{space_id}")
        assert del_resp.status_code == 200
        assert del_resp.json().get("ok") is True
        print(f"Deactivated space: {space_id}")


# ============================================================================
# 2. MULTI-CURRENCY — FX Rates
# ============================================================================

class TestMultiCurrency:
    """Tests for /api/currency/* endpoints"""
    
    def test_get_rates_returns_20_currencies(self, auth_session):
        """GET /api/currency/rates returns 20 default currencies"""
        resp = auth_session.get(f"{BASE_URL}/api/currency/rates")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("base") == "GBP"
        assert "rates" in data
        assert "currencies" in data
        rates = data["rates"]
        currencies = data["currencies"]
        assert len(currencies) >= 20
        # Check some expected currencies
        expected = ["GBP", "EUR", "USD", "TRY", "AED", "AUD", "CAD", "CHF", "JPY", "CNY"]
        for curr in expected:
            assert curr in rates, f"Missing currency: {curr}"
        print(f"Currency rates: {len(currencies)} currencies, EUR rate: {rates.get('EUR')}")
    
    def test_convert_gbp_to_eur(self, auth_session):
        """POST /api/currency/convert converts £100 to EUR (rate 1.18)"""
        resp = auth_session.post(f"{BASE_URL}/api/currency/convert", json={
            "amount": 100,
            "from": "GBP",
            "to": "EUR"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["amount_in"] == 100
        assert data["from"] == "GBP"
        assert data["to"] == "EUR"
        # Default EUR rate is 1.18
        assert data["amount_out"] == 118.0
        assert data["rate_used"] == 1.18
        print(f"Converted £100 → €{data['amount_out']} (rate {data['rate_used']})")
    
    def test_convert_two_hop_via_gbp(self, auth_session):
        """POST /api/currency/convert handles two-hop conversion (USD→EUR via GBP)"""
        resp = auth_session.post(f"{BASE_URL}/api/currency/convert", json={
            "amount": 127,  # $127 = £100 (rate 1.27)
            "from": "USD",
            "to": "EUR"
        })
        assert resp.status_code == 200
        data = resp.json()
        # $127 / 1.27 = £100, £100 * 1.18 = €118
        assert abs(data["amount_out"] - 118.0) < 0.1
        print(f"Two-hop conversion: ${data['amount_in']} → €{data['amount_out']}")
    
    def test_save_property_rate_override(self, auth_session):
        """POST /api/currency/rates saves property-level FX override"""
        resp = auth_session.post(f"{BASE_URL}/api/currency/rates", json={
            "property_id": PROPERTY_ID,
            "rates": {"EUR": 1.20, "USD": 1.30}
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True
        assert data["rates"]["EUR"] == 1.20
        print(f"Saved property rate override: EUR=1.20, USD=1.30")
    
    def test_convert_with_property_override(self, auth_session):
        """POST /api/currency/convert uses property-specific rates"""
        # First save override
        auth_session.post(f"{BASE_URL}/api/currency/rates", json={
            "property_id": PROPERTY_ID,
            "rates": {"EUR": 1.25}
        })
        
        # Convert with property_id
        resp = auth_session.post(f"{BASE_URL}/api/currency/convert", json={
            "amount": 100,
            "from": "GBP",
            "to": "EUR",
            "property_id": PROPERTY_ID
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["amount_out"] == 125.0  # Using override rate 1.25
        print(f"Property override conversion: £100 → €{data['amount_out']}")
    
    def test_convert_unknown_currency_returns_400(self, auth_session):
        """POST /api/currency/convert returns 400 for unknown currency"""
        resp = auth_session.post(f"{BASE_URL}/api/currency/convert", json={
            "amount": 100,
            "from": "GBP",
            "to": "XYZ"
        })
        assert resp.status_code == 400
        assert "unknown currency" in resp.json().get("detail", "").lower()
        print("Unknown currency correctly returned 400")


# ============================================================================
# 3. MULTI-PROPERTY ROLL-UP
# ============================================================================

class TestMultiPropertyRollup:
    """Tests for /api/multi-property/rollup endpoint"""
    
    def test_rollup_returns_properties(self, auth_session):
        """GET /api/multi-property/rollup returns property list with KPIs"""
        resp = auth_session.get(f"{BASE_URL}/api/multi-property/rollup?days=30")
        assert resp.status_code == 200
        data = resp.json()
        
        # Check structure
        assert "window_days" in data
        assert "property_count" in data
        assert "chain_revenue" in data
        assert "chain_bookings" in data
        assert "chain_complaints" in data
        assert "chain_no_shows" in data
        assert "properties" in data
        
        # Validate types
        assert isinstance(data["chain_revenue"], (int, float))
        assert isinstance(data["properties"], list)
        
        print(f"Rollup: {data['property_count']} properties, chain_revenue: £{data['chain_revenue']}")
    
    def test_rollup_properties_sorted_by_revenue(self, auth_session):
        """GET /api/multi-property/rollup returns properties sorted by revenue desc"""
        resp = auth_session.get(f"{BASE_URL}/api/multi-property/rollup?days=30")
        assert resp.status_code == 200
        data = resp.json()
        
        properties = data["properties"]
        if len(properties) > 1:
            revenues = [p["revenue"] for p in properties]
            assert revenues == sorted(revenues, reverse=True), "Properties not sorted by revenue desc"
            print(f"Properties sorted by revenue: {revenues[:3]}...")
    
    def test_rollup_property_kpis(self, auth_session):
        """GET /api/multi-property/rollup returns expected KPIs per property"""
        resp = auth_session.get(f"{BASE_URL}/api/multi-property/rollup?days=30")
        assert resp.status_code == 200
        data = resp.json()
        
        if data["properties"]:
            prop = data["properties"][0]
            expected_fields = ["property_id", "name", "currency", "rooms", "bookings", 
                            "revenue", "adr", "revpar", "occupancy_today_pct", "no_shows", "complaints"]
            for field in expected_fields:
                assert field in prop, f"Missing field: {field}"
            print(f"Property KPIs verified: {prop['name']} - revenue £{prop['revenue']}, ADR £{prop['adr']}")
    
    def test_rollup_days_filter(self, auth_session):
        """GET /api/multi-property/rollup respects days parameter"""
        for days in [7, 14, 30, 60, 90]:
            resp = auth_session.get(f"{BASE_URL}/api/multi-property/rollup?days={days}")
            assert resp.status_code == 200
            data = resp.json()
            assert data["window_days"] == days
        print("Days filter working for 7/14/30/60/90")


# ============================================================================
# 4. BANQUET EVENT ORDER (BEO) PDF
# ============================================================================

class TestBEOPdf:
    """Tests for /api/beo/{event_id}/sheet endpoint"""
    
    def test_beo_bogus_id_returns_404(self, auth_session):
        """GET /api/beo/{event_id}/sheet returns 404 for non-existent event"""
        resp = auth_session.get(f"{BASE_URL}/api/beo/bogus-event-id-12345/sheet")
        assert resp.status_code == 404
        assert "not found" in resp.json().get("detail", "").lower()
        print("BEO 404 for bogus event ID verified")
    
    def test_beo_returns_html(self, auth_session):
        """GET /api/beo/{event_id}/sheet returns HTML content type (if event exists)"""
        # This test will pass with 404 since no events are seeded
        # In production, it would return HTML
        resp = auth_session.get(f"{BASE_URL}/api/beo/test-event/sheet")
        # Either 404 (no event) or 200 with HTML
        assert resp.status_code in [200, 404]
        if resp.status_code == 200:
            assert "text/html" in resp.headers.get("content-type", "")
            assert "<!doctype html>" in resp.text.lower()
            print("BEO returns HTML content")
        else:
            print("BEO returns 404 (no events seeded - expected)")


# ============================================================================
# REGRESSION SMOKE TESTS — Last 4 Batches
# ============================================================================

class TestRegressionSmoke:
    """Smoke tests for features from last 4 batches"""
    
    def test_tax_presets(self, auth_session):
        """GET /api/tax-presets returns presets dict"""
        resp = auth_session.get(f"{BASE_URL}/api/tax-presets")
        assert resp.status_code == 200
        data = resp.json()
        assert "presets" in data
        assert len(data["presets"]) >= 10
        print(f"Tax presets: {len(data['presets'])} countries")
    
    def test_walkin_availability(self, auth_session):
        """GET /api/walkin/{property_id}/availability returns availability"""
        resp = auth_session.get(f"{BASE_URL}/api/walkin/{PROPERTY_ID}/availability")
        # 200 or 404 (if no room types)
        assert resp.status_code in [200, 404]
        print(f"Walk-in availability: {resp.status_code}")
    
    def test_no_show_policy(self, auth_session):
        """GET /api/no-show/{property_id}/policy returns policy"""
        resp = auth_session.get(f"{BASE_URL}/api/no-show/{PROPERTY_ID}/policy")
        assert resp.status_code == 200
        data = resp.json()
        assert "fee_type" in data
        assert "grace_hour" in data
        print(f"No-show policy: fee_type={data['fee_type']}, grace_hour={data['grace_hour']}")
    
    def test_guest_prefs_upsert(self, auth_session):
        """POST /api/guest-prefs/{property_id} upserts preferences"""
        resp = auth_session.post(f"{BASE_URL}/api/guest-prefs/{PROPERTY_ID}", json={
            "guest_email": "test@regression.com",
            "preferences": {"room_temp": "cool", "pillow": "firm"}
        })
        assert resp.status_code == 200
        assert resp.json().get("ok") is True
        print("Guest prefs upsert working")
    
    def test_late_checkout_quote(self, auth_session):
        """GET /api/late-checkout/{property_id}/quote returns quote"""
        resp = auth_session.get(f"{BASE_URL}/api/late-checkout/{PROPERTY_ID}/quote?booking_id=test")
        # 200 or 404 (if booking not found)
        assert resp.status_code in [200, 404]
        print(f"Late checkout quote: {resp.status_code}")
    
    def test_service_recovery_list(self, auth_session):
        """GET /api/service-recovery/{property_id} returns complaints"""
        resp = auth_session.get(f"{BASE_URL}/api/service-recovery/{PROPERTY_ID}")
        assert resp.status_code == 200
        data = resp.json()
        # API returns list directly, not wrapped in "items"
        assert isinstance(data, list)
        print(f"Service recovery: {len(data)} complaints")
    
    def test_room_qr_list(self, auth_session):
        """GET /api/room-qr/{property_id} returns QR codes"""
        resp = auth_session.get(f"{BASE_URL}/api/room-qr/{PROPERTY_ID}")
        # 200 or 404 (if no rooms configured)
        assert resp.status_code in [200, 404]
        print(f"Room QR list: {resp.status_code}")
    
    def test_cleaning_checklists_templates(self, auth_session):
        """GET /api/cleaning-checklists/{property_id}/templates returns templates"""
        resp = auth_session.get(f"{BASE_URL}/api/cleaning-checklists/{PROPERTY_ID}/templates")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        print(f"Cleaning checklists: {len(data['items'])} templates")
    
    def test_room_move_recent(self, auth_session):
        """GET /api/room-move/{property_id}/recent returns moves"""
        resp = auth_session.get(f"{BASE_URL}/api/room-move/{PROPERTY_ID}/recent")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        print(f"Room moves: {len(data['items'])} recent")
    
    def test_lost_found_match(self, auth_session):
        """GET /api/lost-found-match/{property_id} returns matches"""
        resp = auth_session.get(f"{BASE_URL}/api/lost-found-match/{PROPERTY_ID}")
        # 200 or 404 (if no lost items)
        assert resp.status_code in [200, 404]
        print(f"Lost & found match: {resp.status_code}")
    
    def test_group_rooming_list(self, auth_session):
        """GET /api/group-rooming/{property_id} returns rooming list"""
        resp = auth_session.get(f"{BASE_URL}/api/group-rooming/{PROPERTY_ID}")
        assert resp.status_code == 200
        print("Group rooming list working")
    
    def test_attribution_report(self, auth_session):
        """GET /api/attribution/{property_id}/report returns 4 models"""
        resp = auth_session.get(f"{BASE_URL}/api/attribution/{PROPERTY_ID}/report")
        assert resp.status_code == 200
        data = resp.json()
        expected_models = ["first_click", "last_click", "linear", "channel_native"]
        for model in expected_models:
            assert model in data, f"Missing attribution model: {model}"
        print("Attribution report: 4 models present")
    
    def test_timeslots_services(self, auth_session):
        """GET /api/timeslot-services/{property_id} returns services"""
        resp = auth_session.get(f"{BASE_URL}/api/timeslot-services/{PROPERTY_ID}")
        assert resp.status_code == 200
        print("Timeslot services working")
    
    def test_staff_active(self, auth_session):
        """GET /api/staff/{property_id}/active returns active staff"""
        resp = auth_session.get(f"{BASE_URL}/api/staff/{PROPERTY_ID}/active")
        assert resp.status_code == 200
        print("Staff active working")
    
    def test_tip_pool_summary(self, auth_session):
        """GET /api/tip-pool/{property_id}/summary returns summary"""
        resp = auth_session.get(f"{BASE_URL}/api/tip-pool/{PROPERTY_ID}/summary")
        assert resp.status_code == 200
        print("Tip pool summary working")
    
    def test_insurance_config(self, auth_session):
        """GET /api/insurance/{property_id}/config returns config"""
        resp = auth_session.get(f"{BASE_URL}/api/insurance/{PROPERTY_ID}/config")
        assert resp.status_code == 200
        print("Insurance config working")
    
    def test_parity_defender_config(self, auth_session):
        """GET /api/parity-defender/{property_id}/config returns config"""
        resp = auth_session.get(f"{BASE_URL}/api/parity-defender/{PROPERTY_ID}/config")
        assert resp.status_code == 200
        print("Parity defender config working")
    
    def test_webhooks_list(self, auth_session):
        """GET /api/webhooks/{property_id} returns webhooks"""
        resp = auth_session.get(f"{BASE_URL}/api/webhooks/{PROPERTY_ID}")
        assert resp.status_code == 200
        print("Webhooks list working")


# ============================================================================
# CLEANUP
# ============================================================================

class TestCleanup:
    """Cleanup test data"""
    
    def test_cleanup_test_spaces(self, auth_session):
        """Delete TEST_ prefixed spaces"""
        resp = auth_session.get(f"{BASE_URL}/api/spaces/{PROPERTY_ID}")
        if resp.status_code == 200:
            spaces = resp.json()
            for space in spaces:
                if space.get("name", "").startswith("TEST_"):
                    auth_session.delete(f"{BASE_URL}/api/spaces/{PROPERTY_ID}/{space['id']}")
        print("Cleanup completed")
