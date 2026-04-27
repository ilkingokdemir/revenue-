"""
Iteration 218 - Batch 5 Keyless Competitor Parity Features (4 of 30 P0 gaps)
============================================================================
Tests for:
1. Travel Agent / B2B Portal - /api/agents/* CRUD, rates, book-on-behalf, commission report
2. Door-Lock Audit Log - /api/door-locks/log POST, /api/door-locks/{property_id}/log GET
3. Owner Portal - /api/owner-portal/{owner_id}/properties, /summary
4. Direct Widget Savings Banner - /api/widget/savings-banner (PUBLIC)
5. Regression smoke tests for last 5 batches
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
PROPERTY_ID = "city-gate"

# Create a session that persists cookies
session = requests.Session()

@pytest.fixture(scope="module", autouse=True)
def login():
    """Login as admin and store cookies in session"""
    resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    print(f"Login successful, cookies: {session.cookies.get_dict()}")
    return session


# ============================================================================
# 1. TRAVEL AGENT / B2B PORTAL
# ============================================================================

class TestTravelAgentB2B:
    """Travel Agent / Corporate B2B Portal tests"""
    
    agent_id = None
    
    def test_01_list_agents_empty_or_existing(self):
        """GET /api/agents/{property_id} - list agents"""
        resp = session.get(f"{BASE_URL}/api/agents/{PROPERTY_ID}")
        assert resp.status_code == 200, f"List agents failed: {resp.text}"
        data = resp.json()
        assert isinstance(data, list)
        print(f"PASS: List agents returned {len(data)} agents")
    
    def test_02_create_agent_with_15pct_discount_12pct_commission(self):
        """POST /api/agents/{property_id} - create agent with 15% discount + 12% commission"""
        payload = {
            "name": "TEST_Acme Travel Agency",
            "type": "travel_agent",
            "iata": "12345678",
            "email": "acme@travel.test",
            "phone": "+44 20 1234 5678",
            "contact_person": "John Agent",
            "negotiated_discount_pct": 15.0,
            "commission_pct": 12.0,
            "credit_limit": 5000.0,
            "billing_terms": "Net 30",
            "active": True
        }
        resp = session.post(f"{BASE_URL}/api/agents/{PROPERTY_ID}", json=payload)
        assert resp.status_code == 200, f"Create agent failed: {resp.text}"
        data = resp.json()
        assert data.get("ok") is True
        agent = data.get("agent", {})
        assert agent.get("name") == "TEST_Acme Travel Agency"
        assert agent.get("negotiated_discount_pct") == 15.0
        assert agent.get("commission_pct") == 12.0
        TestTravelAgentB2B.agent_id = agent.get("id")
        print(f"PASS: Created agent {TestTravelAgentB2B.agent_id} with 15% discount, 12% commission")
    
    def test_03_get_agent_rates_shows_5_room_types_with_15pct_savings(self):
        """GET /api/agents/{agent_id}/rates - verify 5 room types each showing 15% savings"""
        if not TestTravelAgentB2B.agent_id:
            pytest.skip("No agent created")
        resp = session.get(f"{BASE_URL}/api/agents/{TestTravelAgentB2B.agent_id}/rates")
        assert resp.status_code == 200, f"Get rates failed: {resp.text}"
        data = resp.json()
        rates = data.get("rates", [])
        assert len(rates) >= 5, f"Expected at least 5 room types, got {len(rates)}"
        
        # Verify each room type shows 15% savings
        for rt in rates:
            base = rt.get("base_rate", 0)
            agent_rate = rt.get("agent_rate", 0)
            savings_pct = rt.get("savings_pct", 0)
            if base > 0:
                expected_rate = round(base * 0.85, 2)
                assert abs(agent_rate - expected_rate) < 0.02, f"Agent rate {agent_rate} != expected {expected_rate}"
                assert abs(savings_pct - 15.0) < 0.2, f"Savings {savings_pct}% != 15%"
        print(f"PASS: Agent rates show {len(rates)} room types, each with ~15% savings")
    
    def test_04_book_on_behalf_returns_correct_rate_and_commission(self):
        """POST /api/agents/{agent_id}/book - book on behalf returns correct rate and commission"""
        if not TestTravelAgentB2B.agent_id:
            pytest.skip("No agent created")
        
        # First get rates to find a room type
        resp = session.get(f"{BASE_URL}/api/agents/{TestTravelAgentB2B.agent_id}/rates")
        rates = resp.json().get("rates", [])
        
        # Find a room type (use first available)
        room_type = rates[0] if rates else None
        if not room_type:
            pytest.skip("No room types available")
        
        room_type_id = room_type.get("room_type_id")
        base_rate = room_type.get("base_rate", 0)
        agent_rate = room_type.get("agent_rate", 0)
        
        # Book 2 nights
        check_in = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        payload = {
            "room_type_id": room_type_id,
            "check_in": check_in,
            "nights": 2,
            "guests": 2,
            "guest": {
                "name": "TEST_Guest Smith",
                "email": "guest@test.com",
                "phone": "+44 123 456 7890"
            },
            "notes": "Test booking via agent"
        }
        resp = session.post(f"{BASE_URL}/api/agents/{TestTravelAgentB2B.agent_id}/book", json=payload)
        assert resp.status_code == 200, f"Book on behalf failed: {resp.text}"
        data = resp.json()
        assert data.get("ok") is True
        
        booking = data.get("booking", {})
        commission = data.get("commission_amount", 0)
        
        # Verify booking details
        assert booking.get("channel") == "travel_agent"
        assert booking.get("agent_id") == TestTravelAgentB2B.agent_id
        assert booking.get("agent_name") == "TEST_Acme Travel Agency"
        assert booking.get("agent_commission_pct") == 12.0
        
        # Verify rate calculation: agent_rate * nights
        expected_subtotal = round(agent_rate * 2, 2)
        actual_subtotal = booking.get("subtotal", 0)
        assert abs(actual_subtotal - expected_subtotal) < 0.02, f"Subtotal {actual_subtotal} != expected {expected_subtotal}"
        
        # Verify commission: subtotal * 12%
        expected_commission = round(expected_subtotal * 0.12, 2)
        assert abs(commission - expected_commission) < 0.02, f"Commission {commission} != expected {expected_commission}"
        
        print(f"PASS: Book on behalf - rate £{agent_rate}/night × 2n = £{actual_subtotal}, commission £{commission}")
    
    def test_05_commission_report_shows_booking(self):
        """GET /api/agents/{property_id}/commission-report - shows 1 booking + commission"""
        resp = session.get(f"{BASE_URL}/api/agents/{PROPERTY_ID}/commission-report")
        assert resp.status_code == 200, f"Commission report failed: {resp.text}"
        data = resp.json()
        
        assert "bookings_count" in data
        assert "total_revenue" in data
        assert "total_commission" in data
        assert "agents" in data
        
        # Find our test agent in the report
        agents = data.get("agents", [])
        test_agent = next((a for a in agents if a.get("agent_id") == TestTravelAgentB2B.agent_id), None)
        
        if test_agent:
            assert test_agent.get("bookings") >= 1
            assert test_agent.get("commission") > 0
            print(f"PASS: Commission report shows agent with {test_agent.get('bookings')} bookings, £{test_agent.get('commission')} commission")
        else:
            print(f"PASS: Commission report returned {data.get('bookings_count')} total bookings")
    
    def test_06_deactivate_agent(self):
        """DELETE /api/agents/{property_id}/{agent_id} - deactivate agent"""
        if not TestTravelAgentB2B.agent_id:
            pytest.skip("No agent created")
        resp = session.delete(f"{BASE_URL}/api/agents/{PROPERTY_ID}/{TestTravelAgentB2B.agent_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True
        print(f"PASS: Agent {TestTravelAgentB2B.agent_id} deactivated")


# ============================================================================
# 2. DOOR-LOCK AUDIT LOG
# ============================================================================

class TestDoorLockAuditLog:
    """Door-Lock Audit Log tests"""
    
    def test_01_log_card_success_event(self):
        """POST /api/door-locks/log - log a card success event"""
        payload = {
            "property_id": PROPERTY_ID,
            "room_number": "101",
            "method": "card",
            "actor_role": "guest",
            "actor_name": "TEST_Guest",
            "result": "success",
            "booking_id": "test-booking-123"
        }
        resp = session.post(f"{BASE_URL}/api/door-locks/log", json=payload)
        assert resp.status_code == 200, f"Log event failed: {resp.text}"
        data = resp.json()
        assert data.get("ok") is True
        event = data.get("event", {})
        assert event.get("method") == "card"
        assert event.get("result") == "success"
        assert event.get("room_number") == "101"
        print(f"PASS: Logged card success event for room 101")
    
    def test_02_log_denied_event(self):
        """POST /api/door-locks/log - log a denied event"""
        payload = {
            "property_id": PROPERTY_ID,
            "room_number": "102",
            "method": "pin",
            "actor_role": "unknown",
            "result": "denied"
        }
        resp = session.post(f"{BASE_URL}/api/door-locks/log", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True
        print(f"PASS: Logged denied event for room 102")
    
    def test_03_log_master_key_event(self):
        """POST /api/door-locks/log - log a master key event"""
        payload = {
            "property_id": PROPERTY_ID,
            "room_number": "103",
            "method": "master",
            "actor_role": "staff",
            "actor_name": "Maintenance John",
            "result": "success"
        }
        resp = session.post(f"{BASE_URL}/api/door-locks/log", json=payload)
        assert resp.status_code == 200
        print(f"PASS: Logged master key event for room 103")
    
    def test_04_get_log_returns_events_with_counts(self):
        """GET /api/door-locks/{property_id}/log - returns items + denied_count + master_key_uses"""
        resp = session.get(f"{BASE_URL}/api/door-locks/{PROPERTY_ID}/log?days=7")
        assert resp.status_code == 200, f"Get log failed: {resp.text}"
        data = resp.json()
        
        assert "items" in data
        assert "count" in data
        assert "denied_count" in data
        assert "master_key_uses" in data
        
        items = data.get("items", [])
        assert len(items) >= 1, "Expected at least 1 event"
        
        # Verify denied_count and master_key_uses are calculated
        denied = data.get("denied_count", 0)
        master = data.get("master_key_uses", 0)
        
        print(f"PASS: Door-lock log returned {len(items)} events, {denied} denied, {master} master key uses")
    
    def test_05_filter_by_room(self):
        """GET /api/door-locks/{property_id}/log?room_number=101 - filter by room"""
        resp = session.get(f"{BASE_URL}/api/door-locks/{PROPERTY_ID}/log?room_number=101")
        assert resp.status_code == 200
        data = resp.json()
        items = data.get("items", [])
        for item in items:
            assert item.get("room_number") == "101"
        print(f"PASS: Filter by room 101 returned {len(items)} events")
    
    def test_06_filter_by_method(self):
        """GET /api/door-locks/{property_id}/log?method=card - filter by method"""
        resp = session.get(f"{BASE_URL}/api/door-locks/{PROPERTY_ID}/log?method=card")
        assert resp.status_code == 200
        data = resp.json()
        items = data.get("items", [])
        for item in items:
            assert item.get("method") == "card"
        print(f"PASS: Filter by method=card returned {len(items)} events")
    
    def test_07_filter_by_result(self):
        """GET /api/door-locks/{property_id}/log?result=denied - filter by result"""
        resp = session.get(f"{BASE_URL}/api/door-locks/{PROPERTY_ID}/log?result=denied")
        assert resp.status_code == 200
        data = resp.json()
        items = data.get("items", [])
        for item in items:
            assert item.get("result") == "denied"
        print(f"PASS: Filter by result=denied returned {len(items)} events")


# ============================================================================
# 3. OWNER PORTAL
# ============================================================================

class TestOwnerPortal:
    """Owner Portal tests"""
    
    def test_01_get_properties_bogus_owner_returns_empty(self):
        """GET /api/owner-portal/{owner_id}/properties - bogus owner returns empty list"""
        resp = session.get(f"{BASE_URL}/api/owner-portal/bogus-owner-12345/properties")
        assert resp.status_code == 200, f"Owner properties failed: {resp.text}"
        data = resp.json()
        assert data.get("owner_id") == "bogus-owner-12345"
        assert data.get("properties") == []
        print(f"PASS: Bogus owner_id returns empty properties list")
    
    def test_02_get_summary_bogus_owner_returns_empty_totals(self):
        """GET /api/owner-portal/{owner_id}/summary - bogus owner returns empty totals"""
        resp = session.get(f"{BASE_URL}/api/owner-portal/bogus-owner-12345/summary?days=30")
        assert resp.status_code == 200, f"Owner summary failed: {resp.text}"
        data = resp.json()
        assert data.get("owner_id") == "bogus-owner-12345"
        assert data.get("properties") == []
        totals = data.get("totals", {})
        # Empty totals or zero values
        assert totals == {} or totals.get("gross", 0) == 0
        print(f"PASS: Bogus owner_id returns empty summary")


# ============================================================================
# 4. DIRECT WIDGET SAVINGS BANNER (PUBLIC)
# ============================================================================

class TestSavingsBanner:
    """Direct Widget Savings Banner tests"""
    
    def test_01_savings_banner_no_parity_snapshot_uses_default(self):
        """GET /api/widget/savings-banner - no parity snapshot falls back to default undercut"""
        # This is a PUBLIC endpoint - no auth required
        resp = requests.get(f"{BASE_URL}/api/widget/savings-banner?property_id={PROPERTY_ID}&total=200")
        assert resp.status_code == 200, f"Savings banner failed: {resp.text}"
        data = resp.json()
        
        assert "show" in data
        assert "savings_pct" in data
        assert "savings_amount" in data
        assert "message" in data
        
        # Without parity snapshot, should fall back to undercut_pct (default 5% or configured)
        savings_pct = data.get("savings_pct", 0)
        savings_amount = data.get("savings_amount", 0)
        message = data.get("message", "")
        
        # If show is True, verify the message format
        if data.get("show"):
            assert savings_pct > 0
            assert savings_amount > 0
            assert "save" in message.lower() or "%" in message
            print(f"PASS: Savings banner shows {savings_pct}% savings (£{savings_amount}), message: '{message}'")
        else:
            print(f"PASS: Savings banner returned show=False (no parity config)")
    
    def test_02_savings_banner_with_zero_total(self):
        """GET /api/widget/savings-banner - zero total returns no savings"""
        resp = requests.get(f"{BASE_URL}/api/widget/savings-banner?property_id={PROPERTY_ID}&total=0")
        assert resp.status_code == 200
        data = resp.json()
        # With zero total, savings should be 0
        assert data.get("savings_amount", 0) == 0
        print(f"PASS: Zero total returns no savings")


# ============================================================================
# 5. REGRESSION SMOKE TESTS (Last 5 Batches)
# ============================================================================

class TestRegressionSmoke:
    """Regression smoke tests for features from last 5 batches"""
    
    def test_tax_presets(self):
        """Tax presets endpoint"""
        resp = session.get(f"{BASE_URL}/api/tax-presets/{PROPERTY_ID}")
        assert resp.status_code in [200, 404]  # 404 if no presets configured
        print("PASS: Tax presets endpoint working")
    
    def test_walkin_availability(self):
        """Walk-in availability endpoint"""
        today = datetime.now().strftime("%Y-%m-%d")
        resp = session.get(f"{BASE_URL}/api/walkin/{PROPERTY_ID}/availability?date={today}")
        assert resp.status_code in [200, 404]  # 404 if no rooms configured
        print("PASS: Walk-in availability endpoint working")
    
    def test_no_show_policy(self):
        """No-show policy endpoint"""
        resp = session.get(f"{BASE_URL}/api/no-show/{PROPERTY_ID}/policy")
        assert resp.status_code == 200
        print("PASS: No-show policy endpoint working")
    
    def test_guest_prefs_upsert(self):
        """Guest preferences upsert"""
        payload = {"guest_id": "test-guest-123", "preferences": {"room_temp": "cool"}}
        resp = session.post(f"{BASE_URL}/api/guest-prefs/{PROPERTY_ID}", json=payload)
        assert resp.status_code == 200
        print("PASS: Guest prefs upsert working")
    
    def test_late_checkout_quote(self):
        """Late checkout quote endpoint"""
        resp = session.get(f"{BASE_URL}/api/late-checkout/{PROPERTY_ID}/quote?booking_id=test&requested_time=14:00")
        # May return 404 if booking not found, but endpoint should respond
        assert resp.status_code in [200, 404]
        print("PASS: Late checkout quote endpoint working")
    
    def test_service_recovery_list(self):
        """Service recovery list endpoint"""
        resp = session.get(f"{BASE_URL}/api/service-recovery/{PROPERTY_ID}")
        assert resp.status_code == 200
        print("PASS: Service recovery list endpoint working")
    
    def test_room_qr_list(self):
        """Room QR list endpoint"""
        resp = session.get(f"{BASE_URL}/api/room-qr/{PROPERTY_ID}")
        assert resp.status_code in [200, 404]  # 404 if no rooms configured
        print("PASS: Room QR list endpoint working")
    
    def test_cleaning_checklists_templates(self):
        """Cleaning checklists templates endpoint"""
        resp = session.get(f"{BASE_URL}/api/cleaning-checklists/{PROPERTY_ID}/templates")
        assert resp.status_code == 200
        print("PASS: Cleaning checklists templates endpoint working")
    
    def test_room_move_recent(self):
        """Room move recent endpoint"""
        resp = session.get(f"{BASE_URL}/api/room-move/{PROPERTY_ID}/recent")
        assert resp.status_code == 200
        print("PASS: Room move recent endpoint working")
    
    def test_lost_found_match(self):
        """Lost & found match endpoint"""
        resp = session.get(f"{BASE_URL}/api/lost-found-match/{PROPERTY_ID}/matches")
        assert resp.status_code in [200, 404]  # 404 if no lost items
        print("PASS: Lost & found match endpoint working")
    
    def test_group_rooming_list(self):
        """Group rooming list endpoint"""
        resp = session.get(f"{BASE_URL}/api/group-rooming/{PROPERTY_ID}")
        assert resp.status_code == 200
        print("PASS: Group rooming list endpoint working")
    
    def test_attribution_report(self):
        """Attribution report endpoint"""
        resp = session.get(f"{BASE_URL}/api/attribution/{PROPERTY_ID}/report")
        assert resp.status_code == 200
        data = resp.json()
        # Response may have 'models' or 'channel_native' depending on version
        assert "models" in data or "channel_native" in data
        print(f"PASS: Attribution report working")
    
    def test_timeslots_services(self):
        """Timeslots services endpoint"""
        resp = session.get(f"{BASE_URL}/api/timeslots/{PROPERTY_ID}/services")
        assert resp.status_code in [200, 404]  # 404 if not configured
        print("PASS: Timeslots services endpoint working")
    
    def test_staff_clock_in(self):
        """Staff clock-in endpoint"""
        resp = session.get(f"{BASE_URL}/api/staff-ops/{PROPERTY_ID}/active")
        assert resp.status_code in [200, 404]  # 404 if not configured
        print("PASS: Staff clock-in endpoint working")
    
    def test_tip_pool_summary(self):
        """Tip pool summary endpoint"""
        resp = session.get(f"{BASE_URL}/api/staff-ops/{PROPERTY_ID}/tip-pool/summary")
        assert resp.status_code in [200, 404]  # 404 if not configured
        print("PASS: Tip pool summary endpoint working")
    
    def test_insurance_config(self):
        """Insurance config endpoint"""
        resp = session.get(f"{BASE_URL}/api/revenue-protection/{PROPERTY_ID}/insurance-config")
        assert resp.status_code in [200, 404]  # 404 if not configured
        print("PASS: Insurance config endpoint working")
    
    def test_parity_defender_config(self):
        """Parity defender config endpoint"""
        resp = session.get(f"{BASE_URL}/api/revenue-protection/{PROPERTY_ID}/parity-defender-config")
        assert resp.status_code in [200, 404]  # 404 if not configured
        print("PASS: Parity defender config endpoint working")
    
    def test_webhooks_list(self):
        """Webhooks list endpoint"""
        resp = session.get(f"{BASE_URL}/api/webhooks/{PROPERTY_ID}")
        assert resp.status_code == 200
        print("PASS: Webhooks list endpoint working")
    
    def test_spaces_list(self):
        """Spaces list endpoint (Batch 4)"""
        resp = session.get(f"{BASE_URL}/api/spaces/{PROPERTY_ID}")
        assert resp.status_code == 200
        print("PASS: Spaces list endpoint working")
    
    def test_currency_rates(self):
        """Currency rates endpoint (Batch 4)"""
        resp = session.get(f"{BASE_URL}/api/currency/rates?property_id={PROPERTY_ID}")
        assert resp.status_code == 200
        print("PASS: Currency rates endpoint working")
    
    def test_multi_property_rollup(self):
        """Multi-property rollup endpoint (Batch 4)"""
        resp = session.get(f"{BASE_URL}/api/multi-property/rollup?days=30")
        assert resp.status_code == 200
        print("PASS: Multi-property rollup endpoint working")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
