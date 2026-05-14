"""
Iteration 277: Competitor Parity Sprint v3 - 8 New Modules Testing

Tests for:
1. Booking Engine v2 (packages, upsells, abandoned cart)
2. Owner/Investor Portal
3. Spa & Activities Booking
4. Loyalty Tiers (Silver/Gold/Platinum)
5. Budget vs Actual
6. Compset Auto-Discovery
7. Partner Webhooks & API Keys
8. Automation Analytics
"""
import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


@pytest.fixture(scope="module")
def auth_token():
    """Get admin authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.cookies.get('access_token') or response.json().get('token')
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def session(auth_token):
    """Authenticated session"""
    s = requests.Session()
    s.cookies.set('access_token', auth_token)
    s.headers.update({"Content-Type": "application/json"})
    return s


# ============== BOOKING ENGINE V2 TESTS ==============
class TestBookingEngineV2:
    """Booking Engine v2 - Packages, Upsells, Abandoned Cart"""
    
    def test_list_packages(self, session):
        """GET /api/booking-engine/packages returns packages list"""
        r = session.get(f"{BASE_URL}/api/booking-engine/packages")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "packages" in data
        assert "count" in data
        print(f"✓ List packages: {data['count']} packages found")
    
    def test_create_package(self, session):
        """POST /api/booking-engine/packages creates a package (admin only)"""
        payload = {
            "name": f"TEST_Package_{uuid.uuid4().hex[:6]}",
            "description": "Test package for automation",
            "property_id": "default",
            "discount_percent": 15,
            "extras": [{"name": "Breakfast", "price": 25, "description": "Full English"}],
            "min_nights": 2,
            "max_nights": 7,
            "active": True
        }
        r = session.post(f"{BASE_URL}/api/booking-engine/packages", json=payload)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data["name"] == payload["name"]
        assert data["discount_percent"] == 15
        assert "id" in data
        print(f"✓ Created package: {data['id']}")
        return data["id"]
    
    def test_create_upsell(self, session):
        """POST /api/booking-engine/upsells creates an upsell (admin only)"""
        payload = {
            "name": f"TEST_Upsell_{uuid.uuid4().hex[:6]}",
            "description": "Room upgrade offer",
            "property_id": "default",
            "target": "booking_confirmation",
            "type": "room_upgrade",
            "payload": {"from_room_type": "STD", "to_room_type": "DLX", "upgrade_fee": 35},
            "active": True
        }
        r = session.post(f"{BASE_URL}/api/booking-engine/upsells", json=payload)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data["name"] == payload["name"]
        assert data["target"] == "booking_confirmation"
        print(f"✓ Created upsell: {data['id']}")
    
    def test_track_abandoned_cart_public(self):
        """POST /api/booking-engine/cart/track is public (no auth needed)"""
        payload = {
            "session_id": f"test-session-{uuid.uuid4().hex[:8]}",
            "guest_email": "test@example.com",
            "property_id": "default",
            "step": "payment",
            "details": {"room_type": "DLX", "nights": 3}
        }
        # No auth - public endpoint
        r = requests.post(f"{BASE_URL}/api/booking-engine/cart/track", json=payload)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data["tracked"] == True
        assert "id" in data
        print(f"✓ Tracked abandoned cart (public): {data['id']}")
    
    def test_list_abandoned_carts(self, session):
        """GET /api/booking-engine/cart/abandoned lists carts (admin)"""
        r = session.get(f"{BASE_URL}/api/booking-engine/cart/abandoned?days=14")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "carts" in data
        assert "count" in data
        print(f"✓ List abandoned carts: {data['count']} carts")


# ============== OWNER PORTAL TESTS ==============
class TestOwnerPortal:
    """Owner/Investor Portal - REIT/condo-hotel owners"""
    
    def test_list_owners(self, session):
        """GET /api/owners lists owners (admin)"""
        r = session.get(f"{BASE_URL}/api/owners")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "owners" in data
        assert "count" in data
        print(f"✓ List owners: {data['count']} owners")
    
    def test_create_owner(self, session):
        """POST /api/owners creates owner (admin only)"""
        payload = {
            "name": f"TEST_Owner_{uuid.uuid4().hex[:6]}",
            "email": f"test_owner_{uuid.uuid4().hex[:6]}@example.com",
            "phone": "+44 7700 900000",
            "company": "Test Investment Ltd",
            "management_fee_percent": 20,
            "notes": "Test owner for automation"
        }
        r = session.post(f"{BASE_URL}/api/owners", json=payload)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data["name"] == payload["name"]
        assert data["management_fee_percent"] == 20
        assert "id" in data
        print(f"✓ Created owner: {data['id']}")
        return data["id"]
    
    def test_owner_statement(self, session):
        """GET /api/owners/{id}/statement returns monthly statement"""
        # First create an owner
        owner_id = self.test_create_owner(session)
        
        # Get statement
        month = datetime.now().strftime("%Y-%m")
        r = session.get(f"{BASE_URL}/api/owners/{owner_id}/statement?month={month}")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        
        # Verify statement structure
        assert "gross_revenue" in data
        assert "net_distribution" in data
        assert "management_fee" in data
        assert "owner_share_gross" in data
        assert "operating_costs_est" in data
        assert data["owner_id"] == owner_id
        print(f"✓ Owner statement: gross={data['gross_revenue']}, net={data['net_distribution']}")


# ============== SPA & ACTIVITIES TESTS ==============
class TestSpaActivities:
    """Spa & Activities Booking - services, providers, bookings"""
    
    def test_list_services(self, session):
        """GET /api/spa/services lists services"""
        r = session.get(f"{BASE_URL}/api/spa/services")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "services" in data
        assert "count" in data
        print(f"✓ List spa services: {data['count']} services")
    
    def test_create_service(self, session):
        """POST /api/spa/services creates a service"""
        payload = {
            "name": f"TEST_Massage_{uuid.uuid4().hex[:6]}",
            "category": "spa",
            "duration_minutes": 60,
            "price": 85,
            "description": "Relaxing full body massage",
            "property_id": "default",
            "skills_required": ["massage"],
            "active": True
        }
        r = session.post(f"{BASE_URL}/api/spa/services", json=payload)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data["name"] == payload["name"]
        assert data["duration_minutes"] == 60
        assert data["price"] == 85
        print(f"✓ Created spa service: {data['id']}")
        return data["id"]
    
    def test_create_provider(self, session):
        """POST /api/spa/providers creates a provider"""
        payload = {
            "name": f"TEST_Therapist_{uuid.uuid4().hex[:6]}",
            "role": "therapist",
            "property_id": "default",
            "skills": ["massage", "facial"],
            "working_hours": {"mon": "09:00-18:00", "tue": "09:00-18:00"},
            "active": True
        }
        r = session.post(f"{BASE_URL}/api/spa/providers", json=payload)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data["name"] == payload["name"]
        assert data["role"] == "therapist"
        print(f"✓ Created spa provider: {data['id']}")
        return data["id"]
    
    def test_full_spa_booking_flow(self, session):
        """Full flow: create service → create provider → create booking with auto-allocate"""
        # Create service
        service_payload = {
            "name": f"TEST_Facial_{uuid.uuid4().hex[:6]}",
            "category": "spa",
            "duration_minutes": 45,
            "price": 65,
            "property_id": "default",
            "active": True
        }
        r = session.post(f"{BASE_URL}/api/spa/services", json=service_payload)
        assert r.status_code == 200
        service_id = r.json()["id"]
        
        # Create provider
        provider_payload = {
            "name": f"TEST_Esthetician_{uuid.uuid4().hex[:6]}",
            "role": "esthetician",
            "property_id": "default",
            "active": True
        }
        r = session.post(f"{BASE_URL}/api/spa/providers", json=provider_payload)
        assert r.status_code == 200
        provider_id = r.json()["id"]
        
        # Create booking with auto-allocate (no provider_id)
        booking_payload = {
            "service_id": service_id,
            "guest_name": "Test Guest",
            "guest_email": "testguest@example.com",
            "booking_ref": "BK-TEST-001",
            "start_at": datetime.now().replace(hour=14, minute=0, second=0).isoformat(),
            "notes": "Test booking"
        }
        r = session.post(f"{BASE_URL}/api/spa/bookings", json=booking_payload)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data["service_id"] == service_id
        assert data["provider_id"]  # Should be auto-allocated
        assert data["status"] == "confirmed"
        print(f"✓ Full spa booking flow: service={service_id}, provider auto-allocated={data['provider_id']}")
    
    def test_daily_schedule(self, session):
        """GET /api/spa/schedule returns daily schedule grouped by provider"""
        date = datetime.now().strftime("%Y-%m-%d")
        r = session.get(f"{BASE_URL}/api/spa/schedule?date={date}")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "date" in data
        assert "bookings" in data
        assert "by_provider" in data
        assert "total_revenue" in data
        print(f"✓ Daily schedule: {len(data['bookings'])} bookings, £{data['total_revenue']} revenue")


# ============== LOYALTY TIERS TESTS ==============
class TestLoyaltyTiers:
    """Loyalty Tiers - Silver/Gold/Platinum auto-upgrade"""
    
    def test_get_config_returns_defaults(self, session):
        """GET /api/loyalty-tiers/config returns DEFAULT_TIERS on first call"""
        r = session.get(f"{BASE_URL}/api/loyalty-tiers/config")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "tiers" in data
        assert len(data["tiers"]) >= 3  # Silver, Gold, Platinum
        tier_names = [t["name"] for t in data["tiers"]]
        assert "Silver" in tier_names
        assert "Gold" in tier_names
        assert "Platinum" in tier_names
        print(f"✓ Loyalty config: {len(data['tiers'])} tiers - {tier_names}")
    
    def test_update_tier_config(self, session):
        """PUT /api/loyalty-tiers/config updates tier thresholds"""
        # Get current config
        r = session.get(f"{BASE_URL}/api/loyalty-tiers/config")
        current = r.json()
        
        # Update thresholds
        updated_tiers = current["tiers"].copy()
        for t in updated_tiers:
            if t["name"] == "Gold":
                t["min_stays"] = 6  # Change from 5 to 6
        
        r = session.put(f"{BASE_URL}/api/loyalty-tiers/config", json={"tiers": updated_tiers})
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        assert r.json()["updated"] == True
        
        # Verify update
        r = session.get(f"{BASE_URL}/api/loyalty-tiers/config")
        data = r.json()
        gold_tier = next((t for t in data["tiers"] if t["name"] == "Gold"), None)
        assert gold_tier["min_stays"] == 6
        print(f"✓ Updated loyalty tier config: Gold min_stays={gold_tier['min_stays']}")
    
    def test_list_members(self, session):
        """GET /api/loyalty-tiers/members lists members with computed tiers"""
        r = session.get(f"{BASE_URL}/api/loyalty-tiers/members")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "members" in data
        assert "by_tier" in data
        assert "count" in data
        print(f"✓ Loyalty members: {data['count']} members, by_tier={data['by_tier']}")


# ============== BUDGET VS ACTUAL TESTS ==============
class TestBudgetActual:
    """Budget vs Actual Reports - monthly budget and variance"""
    
    def test_get_budget_returns_12_months(self, session):
        """GET /api/budget/{property_id}/{year} returns 12 month rows"""
        year = datetime.now().strftime("%Y")
        r = session.get(f"{BASE_URL}/api/budget/default/{year}")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "rows" in data
        assert len(data["rows"]) == 12  # 12 months
        assert data["property_id"] == "default"
        assert data["year"] == year
        print(f"✓ Budget grid: {len(data['rows'])} months for {year}")
    
    def test_bulk_update_budget(self, session):
        """PUT /api/budget/{property_id}/{year} bulk updates months"""
        year = datetime.now().strftime("%Y")
        rows = [
            {"month": "01", "revenue_budget": 50000, "rooms_budget": 500, "adr_budget": 100},
            {"month": "02", "revenue_budget": 55000, "rooms_budget": 550, "adr_budget": 100},
        ]
        r = session.put(f"{BASE_URL}/api/budget/default/{year}", json={"rows": rows})
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data["updated"] == 2
        print(f"✓ Updated budget: {data['updated']} months")
    
    def test_get_variance(self, session):
        """GET /api/budget/{property_id}/variance returns actual vs budget"""
        year = datetime.now().strftime("%Y")
        r = session.get(f"{BASE_URL}/api/budget/default/variance?year={year}")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "rows" in data
        assert "totals" in data
        assert len(data["rows"]) == 12
        # Check variance structure
        if data["rows"]:
            row = data["rows"][0]
            assert "revenue_budget" in row
            assert "revenue_actual" in row
            assert "revenue_variance" in row
        print(f"✓ Variance report: totals={data['totals']}")


# ============== COMPSET TESTS ==============
class TestCompset:
    """Compset Auto-Discovery - competitive set management"""
    
    def test_list_compset(self, session):
        """GET /api/compset/{property_id} lists competitive set"""
        r = session.get(f"{BASE_URL}/api/compset/default")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "competitors" in data
        assert "count" in data
        print(f"✓ List compset: {data['count']} competitors")
    
    def test_auto_discover_compset(self, session):
        """POST /api/compset/{property_id}/discover auto-adds up to 5 competitors"""
        r = session.post(f"{BASE_URL}/api/compset/default/discover", json={})
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "added" in data
        assert "count" in data
        assert data["count"] <= 5  # Max 5 per discover
        print(f"✓ Auto-discover: {data['count']} competitors added (MOCKED)")
    
    def test_manual_add_competitor(self, session):
        """POST /api/compset/{property_id}/add manually adds competitor"""
        payload = {
            "name": f"TEST_Hotel_{uuid.uuid4().hex[:6]}",
            "stars": 4,
            "rooms": 100,
            "distance_km": 1.5
        }
        r = session.post(f"{BASE_URL}/api/compset/default/add", json=payload)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data["name"] == payload["name"]
        assert data["source"] == "manual"
        print(f"✓ Manual add competitor: {data['id']}")
    
    def test_snapshot_rates(self, session):
        """GET /api/compset/{property_id}/snapshot returns rates per competitor"""
        r = session.get(f"{BASE_URL}/api/compset/default/snapshot")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "competitors" in data
        # Check snapshot structure
        if data["competitors"]:
            comp = data["competitors"][0]
            assert "last_rate" in comp
            assert "last_availability" in comp
        print(f"✓ Compset snapshot: {len(data['competitors'])} competitors with rates (MOCKED)")


# ============== PARTNER WEBHOOKS & API KEYS TESTS ==============
class TestPartnerWebhooksApiKeys:
    """Partner Webhooks & API Keys - ecosystem integration"""
    
    def test_list_webhooks(self, session):
        """GET /api/partner/webhooks lists subscriptions"""
        r = session.get(f"{BASE_URL}/api/partner/webhooks")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "subscriptions" in data
        assert "events_catalog" in data
        # Verify events catalog
        assert "booking.created" in data["events_catalog"]
        assert "booking.cancelled" in data["events_catalog"]
        print(f"✓ List webhooks: {len(data['subscriptions'])} subs, {len(data['events_catalog'])} events")
    
    def test_create_webhook_valid_events(self, session):
        """POST /api/partner/webhooks creates subscription with valid events"""
        payload = {
            "name": f"TEST_Webhook_{uuid.uuid4().hex[:6]}",
            "url": "https://example.com/webhook",
            "events": ["booking.created", "booking.cancelled"]
        }
        r = session.post(f"{BASE_URL}/api/partner/webhooks", json=payload)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data["name"] == payload["name"]
        assert "secret" in data  # Secret returned once
        assert data["secret"].startswith("whsec_")
        print(f"✓ Created webhook: {data['id']}, secret={data['secret'][:20]}...")
        return data["id"]
    
    def test_create_webhook_invalid_events_rejected(self, session):
        """POST /api/partner/webhooks rejects invalid events"""
        payload = {
            "name": "Invalid Webhook",
            "url": "https://example.com/webhook",
            "events": ["invalid.event", "booking.created"]
        }
        r = session.post(f"{BASE_URL}/api/partner/webhooks", json=payload)
        assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
        print(f"✓ Invalid events rejected: {r.json()}")
    
    def test_webhook_test_ping(self, session):
        """POST /api/partner/webhooks/{id}/test logs delivery"""
        # Create a webhook first
        webhook_id = self.test_create_webhook_valid_events(session)
        
        # Send test ping
        r = session.post(f"{BASE_URL}/api/partner/webhooks/{webhook_id}/test", json={})
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data["sent"] == True
        print(f"✓ Test ping sent (MOCKED - logs delivery only)")
    
    def test_list_deliveries(self, session):
        """GET /api/partner/webhooks/deliveries lists deliveries"""
        r = session.get(f"{BASE_URL}/api/partner/webhooks/deliveries")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "deliveries" in data
        assert "count" in data
        print(f"✓ List deliveries: {data['count']} deliveries")
    
    def test_create_api_key(self, session):
        """POST /api/partner/api-keys creates key (returns secret once)"""
        payload = {
            "name": f"TEST_Key_{uuid.uuid4().hex[:6]}",
            "scopes": ["read", "write"]
        }
        r = session.post(f"{BASE_URL}/api/partner/api-keys", json=payload)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data["name"] == payload["name"]
        assert "secret" in data
        assert data["secret"].startswith("sk_live_")
        assert "prefix" in data
        print(f"✓ Created API key: {data['id']}, prefix={data['prefix']}")
        return data["id"]
    
    def test_revoke_api_key(self, session):
        """DELETE /api/partner/api-keys/{id} revokes key"""
        # Create a key first
        key_id = self.test_create_api_key(session)
        
        # Revoke it
        r = session.delete(f"{BASE_URL}/api/partner/api-keys/{key_id}")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data["revoked"] == 1
        print(f"✓ Revoked API key: {key_id}")


# ============== AUTOMATION ANALYTICS TESTS ==============
class TestAutomationAnalytics:
    """Automation Analytics Dashboard - ROI per rule"""
    
    def test_dashboard(self, session):
        """GET /api/automation/v2/analytics returns dashboard"""
        r = session.get(f"{BASE_URL}/api/automation/v2/analytics?days=30")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "total_rules" in data
        assert "total_runs" in data
        assert "rules" in data
        assert "total_hours_saved" in data
        # Rules should be sorted by runs (descending)
        if len(data["rules"]) > 1:
            assert data["rules"][0]["runs_count"] >= data["rules"][-1]["runs_count"]
        print(f"✓ Analytics dashboard: {data['total_rules']} rules, {data['total_runs']} runs, {data['total_hours_saved']}h saved")
    
    def test_deep_dive_nonexistent_rule(self, session):
        """GET /api/automation/v2/analytics/{rule_id} returns 404 for nonexistent"""
        r = session.get(f"{BASE_URL}/api/automation/v2/analytics/nonexistent-rule-id")
        assert r.status_code == 404, f"Expected 404, got {r.status_code}"
        print(f"✓ Deep dive 404 for nonexistent rule")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
