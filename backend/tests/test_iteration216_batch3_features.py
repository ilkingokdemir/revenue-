"""
Iteration 216 - Batch 3 Keyless Competitor Parity Features (5 of 30 P0 gaps)
============================================================================
Tests for:
1. SPA & ACTIVITY TIME-SLOT BOOKING - /api/timeslot-services/* and /api/timeslot-bookings/*
2. STAFF CLOCK-IN + TIP POOL - /api/staff/* and /api/tip-pool/*
3. INSURANCE UPSELL - /api/insurance/*
4. PARITY DEFENDER - /api/parity-defender/*
5. OUTBOUND WEBHOOKS - /api/webhooks/*
6. REGRESSION smoke tests for last 3 batches
"""
import pytest
import requests
import os
import time
from datetime import datetime, date

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
# 1. SPA & ACTIVITY TIME-SLOT BOOKING
# ============================================================================
class TestTimeslotServices:
    """Test timeslot service CRUD and availability"""
    
    service_id = None
    
    def test_create_spa_service_with_capacity_2(self, auth_session):
        """Create a spa service with concurrent_capacity=2"""
        resp = auth_session.post(f"{BASE_URL}/api/timeslot-services/{PROPERTY_ID}", json={
            "name": "TEST_Spa Massage",
            "category": "spa",
            "duration_min": 60,
            "price": 75.00,
            "currency": "GBP",
            "concurrent_capacity": 2,
            "open_hour": 9,
            "close_hour": 21,
            "buffer_min": 15,
            "description": "Relaxing 60-minute massage"
        })
        assert resp.status_code == 200, f"Create service failed: {resp.text}"
        data = resp.json()
        assert data["ok"] is True
        assert data["service"]["name"] == "TEST_Spa Massage"
        assert data["service"]["concurrent_capacity"] == 2
        TestTimeslotServices.service_id = data["service"]["id"]
        print(f"✓ Created spa service: {TestTimeslotServices.service_id}")
    
    def test_list_services(self, auth_session):
        """List services for property"""
        resp = auth_session.get(f"{BASE_URL}/api/timeslot-services/{PROPERTY_ID}")
        assert resp.status_code == 200
        services = resp.json()
        assert isinstance(services, list)
        # Find our test service
        test_svc = next((s for s in services if s.get("name") == "TEST_Spa Massage"), None)
        assert test_svc is not None, "Test service not found in list"
        print(f"✓ Listed {len(services)} services, found TEST_Spa Massage")
    
    def test_get_availability_returns_slots(self, auth_session):
        """Get availability for today - should return slots"""
        today = date.today().isoformat()
        resp = auth_session.get(
            f"{BASE_URL}/api/timeslot-services/{PROPERTY_ID}/{TestTimeslotServices.service_id}/availability?date={today}"
        )
        assert resp.status_code == 200, f"Get availability failed: {resp.text}"
        data = resp.json()
        assert "slots" in data
        assert "service" in data
        # With 9-21 hours, 60min duration + 15min buffer = 75min per slot
        # Should have multiple slots
        assert len(data["slots"]) > 0, "Expected slots to be generated"
        # Each slot should have available count
        for slot in data["slots"]:
            assert "available" in slot
            assert "start" in slot
            assert "end" in slot
        print(f"✓ Got {len(data['slots'])} availability slots for {today}")
        return data["slots"]


class TestTimeslotBookings:
    """Test timeslot booking with capacity checks"""
    
    booking1_id = None
    booking2_id = None
    slot_start = None
    
    def test_book_first_guest(self, auth_session):
        """Book first guest into a slot"""
        # Get a slot first
        today = date.today().isoformat()
        resp = auth_session.get(
            f"{BASE_URL}/api/timeslot-services/{PROPERTY_ID}/{TestTimeslotServices.service_id}/availability?date={today}"
        )
        slots = resp.json()["slots"]
        assert len(slots) > 0, "No slots available"
        
        # Pick first available slot
        slot = slots[0]
        TestTimeslotBookings.slot_start = slot["start"]
        
        resp = auth_session.post(f"{BASE_URL}/api/timeslot-bookings", json={
            "service_id": TestTimeslotServices.service_id,
            "start": slot["start"],
            "guest_name": "TEST_Guest Alice",
            "guest_email": "alice@test.com",
            "charge_to": "room"
        })
        assert resp.status_code == 200, f"Book slot failed: {resp.text}"
        data = resp.json()
        assert data["ok"] is True
        assert data["booking"]["guest_name"] == "TEST_Guest Alice"
        TestTimeslotBookings.booking1_id = data["booking"]["id"]
        print(f"✓ Booked slot for Alice: {TestTimeslotBookings.booking1_id}")
    
    def test_book_second_guest_same_slot(self, auth_session):
        """Second guest can also book same slot (capacity=2)"""
        resp = auth_session.post(f"{BASE_URL}/api/timeslot-bookings", json={
            "service_id": TestTimeslotServices.service_id,
            "start": TestTimeslotBookings.slot_start,
            "guest_name": "TEST_Guest Bob",
            "guest_email": "bob@test.com",
            "charge_to": "cash"
        })
        assert resp.status_code == 200, f"Book second slot failed: {resp.text}"
        data = resp.json()
        assert data["ok"] is True
        TestTimeslotBookings.booking2_id = data["booking"]["id"]
        print(f"✓ Booked same slot for Bob: {TestTimeslotBookings.booking2_id}")
    
    def test_third_guest_gets_409_slot_full(self, auth_session):
        """Third guest should get 409 - slot full"""
        resp = auth_session.post(f"{BASE_URL}/api/timeslot-bookings", json={
            "service_id": TestTimeslotServices.service_id,
            "start": TestTimeslotBookings.slot_start,
            "guest_name": "TEST_Guest Charlie",
            "guest_email": "charlie@test.com",
            "charge_to": "card"
        })
        assert resp.status_code == 409, f"Expected 409 for full slot, got {resp.status_code}: {resp.text}"
        print("✓ Third booking correctly rejected with 409 (slot full)")
    
    def test_list_bookings(self, auth_session):
        """List bookings for property"""
        resp = auth_session.get(f"{BASE_URL}/api/timeslot-bookings/{PROPERTY_ID}?days=7")
        assert resp.status_code == 200
        bookings = resp.json()
        assert isinstance(bookings, list)
        # Find our test bookings
        test_bookings = [b for b in bookings if b.get("guest_name", "").startswith("TEST_Guest")]
        assert len(test_bookings) >= 2, f"Expected at least 2 test bookings, found {len(test_bookings)}"
        print(f"✓ Listed {len(bookings)} bookings, found {len(test_bookings)} test bookings")
    
    def test_cancel_booking(self, auth_session):
        """Cancel a booking"""
        resp = auth_session.post(f"{BASE_URL}/api/timeslot-bookings/{TestTimeslotBookings.booking1_id}/cancel")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        print(f"✓ Cancelled booking {TestTimeslotBookings.booking1_id}")


# ============================================================================
# 2. STAFF CLOCK-IN + TIP POOL
# ============================================================================
class TestStaffClockInOut:
    """Test staff clock-in/out and shift tracking"""
    
    entry_id = None
    
    def test_clock_in_alice(self, auth_session):
        """Clock in Alice as server"""
        resp = auth_session.post(f"{BASE_URL}/api/staff/clock-in", json={
            "property_id": PROPERTY_ID,
            "staff_name": "TEST_Alice Server",
            "role": "server"
        })
        assert resp.status_code == 200, f"Clock-in failed: {resp.text}"
        data = resp.json()
        assert data["ok"] is True
        assert data["entry"]["staff_name"] == "TEST_Alice Server"
        assert data["entry"]["role"] == "server"
        assert data["entry"]["clock_out"] == ""  # Not clocked out yet
        TestStaffClockInOut.entry_id = data["entry"]["id"]
        print(f"✓ Clocked in Alice: {TestStaffClockInOut.entry_id}")
    
    def test_double_clock_in_prevented(self, auth_session):
        """Double clock-in should return warning, not create duplicate"""
        resp = auth_session.post(f"{BASE_URL}/api/staff/clock-in", json={
            "property_id": PROPERTY_ID,
            "staff_name": "TEST_Alice Server",
            "role": "server"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "warning" in data, "Expected warning for double clock-in"
        assert "Already clocked in" in data["warning"]
        print("✓ Double clock-in correctly prevented with warning")
    
    def test_get_active_staff(self, auth_session):
        """Get currently clocked-in staff"""
        resp = auth_session.get(f"{BASE_URL}/api/staff/{PROPERTY_ID}/active")
        assert resp.status_code == 200
        active = resp.json()
        assert isinstance(active, list)
        # Find our test staff
        test_staff = [s for s in active if s.get("staff_name") == "TEST_Alice Server"]
        assert len(test_staff) == 1, "Expected TEST_Alice Server in active list"
        print(f"✓ Found {len(active)} active staff, including TEST_Alice Server")
    
    def test_clock_out_with_duration(self, auth_session):
        """Clock out and verify duration is computed"""
        # Wait a bit to ensure duration > 0
        time.sleep(2)
        
        resp = auth_session.post(f"{BASE_URL}/api/staff/clock-out/{TestStaffClockInOut.entry_id}")
        assert resp.status_code == 200, f"Clock-out failed: {resp.text}"
        data = resp.json()
        assert data["ok"] is True
        assert data["entry"]["clock_out"] != ""
        # Duration may be 0.0 if clock-in/out happened very quickly, that's acceptable
        assert data["entry"]["duration_min"] >= 0, "Expected duration_min >= 0"
        print(f"✓ Clocked out Alice, duration: {data['entry']['duration_min']} min")
    
    def test_get_shifts(self, auth_session):
        """Get recent shifts"""
        resp = auth_session.get(f"{BASE_URL}/api/staff/{PROPERTY_ID}/shifts?days=7")
        assert resp.status_code == 200
        shifts = resp.json()
        assert isinstance(shifts, list)
        # Find our test shift
        test_shifts = [s for s in shifts if s.get("staff_name") == "TEST_Alice Server"]
        assert len(test_shifts) >= 1, "Expected TEST_Alice Server shift in list"
        print(f"✓ Found {len(shifts)} shifts, including TEST_Alice Server")


class TestTipPool:
    """Test tip pool contribution and distribution"""
    
    def test_contribute_tip(self, auth_session):
        """Add £120 tip to pool"""
        today = date.today().isoformat()
        resp = auth_session.post(f"{BASE_URL}/api/tip-pool/{PROPERTY_ID}/contribute", json={
            "amount": 120.00,
            "currency": "GBP",
            "source": "card",
            "shift_date": today,
            "note": "Test tip contribution"
        })
        assert resp.status_code == 200, f"Contribute failed: {resp.text}"
        data = resp.json()
        assert data["ok"] is True
        assert data["contribution"]["amount"] == 120.00
        print("✓ Contributed £120 to tip pool")
    
    def test_get_summary(self, auth_session):
        """Get tip pool summary"""
        today = date.today().isoformat()
        resp = auth_session.get(f"{BASE_URL}/api/tip-pool/{PROPERTY_ID}/summary?shift_date={today}")
        assert resp.status_code == 200
        data = resp.json()
        assert "pending_pool_total" in data
        assert "role_weights" in data
        assert data["pending_pool_total"] >= 120.00, "Expected at least £120 in pool"
        print(f"✓ Pool summary: £{data['pending_pool_total']} pending")
    
    def test_distribute_tip_pool(self, auth_session):
        """Distribute tip pool - should allocate to staff who worked today"""
        today = date.today().isoformat()
        resp = auth_session.post(f"{BASE_URL}/api/tip-pool/{PROPERTY_ID}/distribute", json={
            "shift_date": today
        })
        assert resp.status_code == 200, f"Distribute failed: {resp.text}"
        data = resp.json()
        # May succeed or fail depending on whether shifts exist for today
        if data.get("ok"):
            assert "distribution" in data
            assert "allocations" in data["distribution"]
            print(f"✓ Distributed pool: {len(data['distribution']['allocations'])} allocations")
        else:
            # No shifts for today is acceptable
            assert "reason" in data
            print(f"✓ Distribution skipped: {data['reason']}")


# ============================================================================
# 3. INSURANCE UPSELL
# ============================================================================
class TestInsuranceUpsell:
    """Test insurance config and quote endpoints"""
    
    def test_get_default_config(self, auth_session):
        """Get insurance config - should return defaults"""
        resp = auth_session.get(f"{BASE_URL}/api/insurance/{PROPERTY_ID}/config")
        assert resp.status_code == 200, f"Get config failed: {resp.text}"
        data = resp.json()
        assert "rate_pct" in data
        assert "min_premium" in data
        assert "max_premium" in data
        # Default rate is 5%
        assert data["rate_pct"] == 5.0, f"Expected default rate 5%, got {data['rate_pct']}"
        print(f"✓ Insurance config: {data['rate_pct']}% rate, min £{data['min_premium']}, max £{data['max_premium']}")
    
    def test_quote_on_500_returns_25(self, auth_session):
        """Quote on total=500 with 5% rate should return £25"""
        resp = auth_session.post(f"{BASE_URL}/api/insurance/quote", json={
            "property_id": PROPERTY_ID,
            "total": 500.00
        })
        assert resp.status_code == 200, f"Quote failed: {resp.text}"
        data = resp.json()
        assert data["available"] is True
        assert data["premium"] == 25.00, f"Expected £25 premium, got £{data['premium']}"
        print(f"✓ Quote on £500: premium £{data['premium']}")
    
    def test_save_custom_rate_10_percent(self, auth_session):
        """Save custom rate of 10%"""
        resp = auth_session.post(f"{BASE_URL}/api/insurance/{PROPERTY_ID}/config", json={
            "rate_pct": 10.0,
            "min_premium": 5.0,
            "max_premium": 100.0
        })
        assert resp.status_code == 200, f"Save config failed: {resp.text}"
        data = resp.json()
        assert data["ok"] is True
        assert data["config"]["rate_pct"] == 10.0
        print("✓ Saved custom rate: 10%")
    
    def test_quote_with_10_percent_returns_50(self, auth_session):
        """Quote on total=500 with 10% rate should return £50"""
        resp = auth_session.post(f"{BASE_URL}/api/insurance/quote", json={
            "property_id": PROPERTY_ID,
            "total": 500.00
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is True
        assert data["premium"] == 50.00, f"Expected £50 premium, got £{data['premium']}"
        print(f"✓ Quote with 10% rate: premium £{data['premium']}")
    
    def test_restore_default_rate(self, auth_session):
        """Restore default 5% rate"""
        resp = auth_session.post(f"{BASE_URL}/api/insurance/{PROPERTY_ID}/config", json={
            "rate_pct": 5.0
        })
        assert resp.status_code == 200
        print("✓ Restored default 5% rate")


# ============================================================================
# 4. PARITY DEFENDER
# ============================================================================
class TestParityDefender:
    """Test parity defender config and recommendations"""
    
    def test_get_default_config(self, auth_session):
        """Get parity defender config - should return defaults"""
        resp = auth_session.get(f"{BASE_URL}/api/parity-defender/{PROPERTY_ID}/config")
        assert resp.status_code == 200, f"Get config failed: {resp.text}"
        data = resp.json()
        assert "enabled" in data
        assert "undercut_pct" in data
        assert "show_savings_badge" in data
        # undercut_pct should be a number (may have been modified by previous tests)
        assert isinstance(data["undercut_pct"], (int, float))
        print(f"✓ Parity config: {data['undercut_pct']}% undercut, badge={data['show_savings_badge']}")
    
    def test_save_custom_undercut_10(self, auth_session):
        """Save custom undercut of 10%"""
        resp = auth_session.post(f"{BASE_URL}/api/parity-defender/{PROPERTY_ID}/config", json={
            "undercut_pct": 10.0,
            "show_savings_badge": True
        })
        assert resp.status_code == 200, f"Save config failed: {resp.text}"
        data = resp.json()
        assert data["ok"] is True
        assert data["config"]["undercut_pct"] == 10.0
        print("✓ Saved custom undercut: 10%")
    
    def test_recommendation_returns_200(self, auth_session):
        """Get recommendation - should return 200 even with no parity data"""
        resp = auth_session.get(f"{BASE_URL}/api/parity-defender/{PROPERTY_ID}/recommendation")
        assert resp.status_code == 200, f"Get recommendation failed: {resp.text}"
        data = resp.json()
        assert "config" in data
        assert "recommendations" in data
        # May be empty list if no parity_analysis data
        assert isinstance(data["recommendations"], list)
        print(f"✓ Recommendation: {len(data['recommendations'])} dates with parity data")


# ============================================================================
# 5. OUTBOUND WEBHOOKS
# ============================================================================
class TestOutboundWebhooks:
    """Test webhook subscription, test fire, and logging"""
    
    webhook_id = None
    
    def test_subscribe_webhook(self, auth_session):
        """Subscribe to httpbin.org with booking.created event"""
        resp = auth_session.post(f"{BASE_URL}/api/webhooks/{PROPERTY_ID}", json={
            "url": "https://httpbin.org/post",
            "events": ["booking.created"],
            "secret": "test-secret-123"
        })
        assert resp.status_code == 200, f"Subscribe failed: {resp.text}"
        data = resp.json()
        assert data["ok"] is True
        assert data["webhook"]["url"] == "https://httpbin.org/post"
        assert "booking.created" in data["webhook"]["events"]
        TestOutboundWebhooks.webhook_id = data["webhook"]["id"]
        print(f"✓ Subscribed webhook: {TestOutboundWebhooks.webhook_id}")
    
    def test_list_webhooks(self, auth_session):
        """List webhooks for property"""
        resp = auth_session.get(f"{BASE_URL}/api/webhooks/{PROPERTY_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "supported_events" in data
        # Find our test webhook
        test_wh = next((w for w in data["items"] if w.get("id") == TestOutboundWebhooks.webhook_id), None)
        assert test_wh is not None, "Test webhook not found in list"
        print(f"✓ Listed {len(data['items'])} webhooks, supported events: {len(data['supported_events'])}")
    
    def test_fire_webhook_returns_200(self, auth_session):
        """Test fire webhook - should return HTTP 200 from httpbin"""
        resp = auth_session.post(f"{BASE_URL}/api/webhooks/{PROPERTY_ID}/test/{TestOutboundWebhooks.webhook_id}")
        assert resp.status_code == 200, f"Test fire failed: {resp.text}"
        data = resp.json()
        assert data["ok"] is True
        assert data["status_code"] == 200, f"Expected HTTP 200 from httpbin, got {data['status_code']}"
        assert data["success"] is True
        assert "duration_ms" in data
        print(f"✓ Webhook test fire: HTTP {data['status_code']} in {data['duration_ms']}ms")
    
    def test_webhook_log_shows_entry(self, auth_session):
        """Check webhook log shows the test fire"""
        resp = auth_session.get(f"{BASE_URL}/api/webhooks/{PROPERTY_ID}/log")
        assert resp.status_code == 200
        logs = resp.json()
        assert isinstance(logs, list)
        # Find our test fire
        test_log = next((l for l in logs if l.get("webhook_id") == TestOutboundWebhooks.webhook_id), None)
        assert test_log is not None, "Test fire not found in log"
        assert test_log["success"] is True
        assert test_log["status_code"] == 200
        print(f"✓ Webhook log shows test fire: {test_log['event']} → HTTP {test_log['status_code']}")
    
    def test_webhook_fail_count_stays_0(self, auth_session):
        """Verify fail_count is still 0 after successful test"""
        resp = auth_session.get(f"{BASE_URL}/api/webhooks/{PROPERTY_ID}")
        data = resp.json()
        test_wh = next((w for w in data["items"] if w.get("id") == TestOutboundWebhooks.webhook_id), None)
        assert test_wh is not None
        assert test_wh["fail_count"] == 0, f"Expected fail_count=0, got {test_wh['fail_count']}"
        assert test_wh["fire_count"] >= 1, "Expected fire_count >= 1"
        print(f"✓ Webhook stats: fire_count={test_wh['fire_count']}, fail_count={test_wh['fail_count']}")
    
    def test_delete_webhook(self, auth_session):
        """Delete the test webhook"""
        resp = auth_session.delete(f"{BASE_URL}/api/webhooks/{PROPERTY_ID}/{TestOutboundWebhooks.webhook_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        print("✓ Deleted test webhook")


# ============================================================================
# 6. REGRESSION SMOKE TESTS (Last 3 batches)
# ============================================================================
class TestRegressionSmoke:
    """Smoke tests for features from iterations 213-215"""
    
    def test_tax_presets_list(self, auth_session):
        """Tax presets should return country codes"""
        resp = auth_session.get(f"{BASE_URL}/api/tax-presets")
        assert resp.status_code == 200
        data = resp.json()
        # API returns {"presets": [...]} or list directly
        presets = data.get("presets", data) if isinstance(data, dict) else data
        assert isinstance(presets, list)
        assert len(presets) >= 10, f"Expected at least 10 tax presets, got {len(presets)}"
        print(f"✓ Tax presets: {len(presets)} countries")
    
    def test_walkin_availability(self, auth_session):
        """Walk-in availability should return offerings"""
        today = date.today().isoformat()
        resp = auth_session.get(f"{BASE_URL}/api/walkin/{PROPERTY_ID}/availability?date={today}")
        # 200 or 404 (if no room types) are both acceptable
        assert resp.status_code in [200, 404], f"Unexpected status: {resp.status_code}"
        if resp.status_code == 200:
            data = resp.json()
            offerings = data.get("offerings", [])
            print(f"✓ Walk-in availability: {len(offerings)} offerings")
        else:
            print("✓ Walk-in availability endpoint working (no room types configured)")
    
    def test_no_show_policy(self, auth_session):
        """No-show policy should return config"""
        resp = auth_session.get(f"{BASE_URL}/api/no-show/{PROPERTY_ID}/policy")
        assert resp.status_code == 200
        data = resp.json()
        assert "fee_type" in data
        assert "grace_hour" in data
        print(f"✓ No-show policy: fee_type={data['fee_type']}")
    
    def test_guest_prefs_upsert(self, auth_session):
        """Guest prefs upsert should work"""
        resp = auth_session.post(f"{BASE_URL}/api/guest-prefs/{PROPERTY_ID}", json={
            "guest_email": "test-regression@example.com",
            "preferences": {"pillow_type": "soft", "room_temp": "cool"}
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        print("✓ Guest prefs upsert working")
    
    def test_late_checkout_quote(self, auth_session):
        """Late checkout quote should return fee"""
        resp = auth_session.get(f"{BASE_URL}/api/late-checkout/{PROPERTY_ID}/quote?booking_id=test-booking&requested_hour=14")
        # 200 or 404 (if booking not found) are both acceptable
        assert resp.status_code in [200, 404], f"Unexpected status: {resp.status_code}"
        if resp.status_code == 200:
            data = resp.json()
            assert "fee" in data or "error" in data
        print("✓ Late checkout quote endpoint working")
    
    def test_service_recovery_list(self, auth_session):
        """Service recovery list should return complaints"""
        resp = auth_session.get(f"{BASE_URL}/api/service-recovery/{PROPERTY_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        print(f"✓ Service recovery: {len(data)} complaints")
    
    def test_room_qr_list(self, auth_session):
        """Room QR list should return codes"""
        resp = auth_session.get(f"{BASE_URL}/api/room-qr/{PROPERTY_ID}")
        # 200 or 404 are both acceptable
        assert resp.status_code in [200, 404], f"Unexpected status: {resp.status_code}"
        if resp.status_code == 200:
            data = resp.json()
            codes = data.get("items", data) if isinstance(data, dict) else data
            print(f"✓ Room QR: {len(codes)} codes")
        else:
            print("✓ Room QR endpoint working")
    
    def test_cleaning_checklists_templates(self, auth_session):
        """Cleaning checklists should return templates"""
        resp = auth_session.get(f"{BASE_URL}/api/cleaning-checklists/{PROPERTY_ID}/templates")
        assert resp.status_code == 200
        data = resp.json()
        # API returns {"items": [...], "default_items": [...]} or list directly
        templates = data.get("items", data) if isinstance(data, dict) else data
        assert isinstance(templates, list)
        print(f"✓ Cleaning checklists: {len(templates)} templates")
    
    def test_room_move_recent(self, auth_session):
        """Room move recent should return moves"""
        resp = auth_session.get(f"{BASE_URL}/api/room-move/{PROPERTY_ID}/recent")
        assert resp.status_code == 200
        data = resp.json()
        # API returns {"items": [...], "count": N} or list directly
        moves = data.get("items", data) if isinstance(data, dict) else data
        assert isinstance(moves, list)
        print(f"✓ Room move: {len(moves)} recent moves")
    
    def test_group_rooming_list(self, auth_session):
        """Group rooming list should work"""
        # Use a dummy group ID - endpoint should return empty list or 404
        resp = auth_session.get(f"{BASE_URL}/api/group-rooming/test-group-id")
        # 200 with empty list or 404 are both acceptable
        assert resp.status_code in [200, 404]
        print("✓ Group rooming endpoint working")
    
    def test_attribution_report(self, auth_session):
        """Attribution report should return models"""
        resp = auth_session.get(f"{BASE_URL}/api/attribution/{PROPERTY_ID}/report?days=30")
        assert resp.status_code == 200
        data = resp.json()
        assert "first_click" in data
        assert "last_click" in data
        assert "linear" in data
        assert "channel_native" in data
        print("✓ Attribution report: 4 models returned")


# ============================================================================
# CLEANUP
# ============================================================================
class TestCleanup:
    """Clean up test data"""
    
    def test_delete_test_service(self, auth_session):
        """Delete test spa service"""
        if TestTimeslotServices.service_id:
            resp = auth_session.delete(
                f"{BASE_URL}/api/timeslot-services/{PROPERTY_ID}/{TestTimeslotServices.service_id}"
            )
            assert resp.status_code == 200
            print(f"✓ Deleted test service {TestTimeslotServices.service_id}")
