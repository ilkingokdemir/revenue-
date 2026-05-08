"""
Batch 8 P1 Keyless Features Tests (6-10 of 20)
----------------------------------------------
1. Service Recovery Voucher - Auto-tiered vouchers for low-score guests
2. Folio Split-Billing - Multi-payer folio allocation with caps
3. Loyalty Auto-Tier - Automatic tier upgrades based on stays/revenue
4. Late-Checkout Offer Engine - Dynamic pricing for late checkout
5. OTA Stop-Sell Forecast - Predict when to stop OTA sales
"""
import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
PROPERTY_ID = "default"

@pytest.fixture(scope="module")
def auth_token():
    """Get admin auth token"""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    if resp.status_code != 200:
        pytest.skip(f"Auth failed: {resp.status_code} - {resp.text}")
    return resp.json().get("token")

@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Auth headers for requests"""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


# ============================================================================
# SERVICE RECOVERY VOUCHER TESTS
# ============================================================================
class TestServiceRecoveryVoucher:
    """Service Recovery Auto-Voucher endpoints"""
    
    def test_issue_voucher_score_1(self, auth_headers):
        """POST /api/service-recovery/voucher - score 1 gets 25%/£200"""
        resp = requests.post(f"{BASE_URL}/api/service-recovery/voucher", headers=auth_headers, json={
            "property_id": PROPERTY_ID,
            "guest_email": f"test_sr_{uuid.uuid4().hex[:8]}@test.com",
            "guest_name": "Test Guest Score1",
            "score": 1
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["ok"] is True
        voucher = data["voucher"]
        assert voucher["percent_off"] == 25.0, f"Score 1 should get 25%, got {voucher['percent_off']}"
        assert voucher["max_amount_off"] == 200.0, f"Score 1 should get £200 max, got {voucher['max_amount_off']}"
        assert voucher["code"].startswith("SR-")
        assert voucher["redeemed"] is False
    
    def test_issue_voucher_score_2(self, auth_headers):
        """POST /api/service-recovery/voucher - score 2 gets 20%/£150"""
        resp = requests.post(f"{BASE_URL}/api/service-recovery/voucher", headers=auth_headers, json={
            "property_id": PROPERTY_ID,
            "guest_email": f"test_sr_{uuid.uuid4().hex[:8]}@test.com",
            "guest_name": "Test Guest Score2",
            "score": 2
        })
        assert resp.status_code == 200
        voucher = resp.json()["voucher"]
        assert voucher["percent_off"] == 20.0, f"Score 2 should get 20%, got {voucher['percent_off']}"
        assert voucher["max_amount_off"] == 150.0, f"Score 2 should get £150 max, got {voucher['max_amount_off']}"
    
    def test_issue_voucher_score_3_plus(self, auth_headers):
        """POST /api/service-recovery/voucher - score 3+ gets 15%/£100"""
        resp = requests.post(f"{BASE_URL}/api/service-recovery/voucher", headers=auth_headers, json={
            "property_id": PROPERTY_ID,
            "guest_email": f"test_sr_{uuid.uuid4().hex[:8]}@test.com",
            "guest_name": "Test Guest Score3",
            "score": 3
        })
        assert resp.status_code == 200
        voucher = resp.json()["voucher"]
        assert voucher["percent_off"] == 15.0, f"Score 3+ should get 15%, got {voucher['percent_off']}"
        assert voucher["max_amount_off"] == 100.0, f"Score 3+ should get £100 max, got {voucher['max_amount_off']}"
    
    def test_list_vouchers(self, auth_headers):
        """GET /api/service-recovery/{prop}/vouchers - lists with redeem_rate KPI"""
        resp = requests.get(f"{BASE_URL}/api/service-recovery/{PROPERTY_ID}/vouchers", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "count" in data
        assert "redeemed_count" in data
        assert "redeem_rate" in data
    
    def test_public_voucher_lookup(self, auth_headers):
        """GET /api/service-recovery/voucher/{code} - PUBLIC (no auth)"""
        # First issue a voucher
        resp = requests.post(f"{BASE_URL}/api/service-recovery/voucher", headers=auth_headers, json={
            "property_id": PROPERTY_ID,
            "guest_email": f"test_public_{uuid.uuid4().hex[:8]}@test.com",
            "score": 2
        })
        assert resp.status_code == 200
        code = resp.json()["voucher"]["code"]
        
        # Public lookup (no auth)
        resp2 = requests.get(f"{BASE_URL}/api/service-recovery/voucher/{code}")
        assert resp2.status_code == 200, f"Public lookup failed: {resp2.status_code}"
        data = resp2.json()
        assert data["code"] == code
        assert data["valid"] is True
        assert data["redeemed"] is False
        assert "percent_off" in data
    
    def test_redeem_voucher(self, auth_headers):
        """POST /api/service-recovery/voucher/{code}/redeem - marks used"""
        # Issue voucher
        resp = requests.post(f"{BASE_URL}/api/service-recovery/voucher", headers=auth_headers, json={
            "property_id": PROPERTY_ID,
            "guest_email": f"test_redeem_{uuid.uuid4().hex[:8]}@test.com",
            "score": 3
        })
        code = resp.json()["voucher"]["code"]
        
        # Redeem
        resp2 = requests.post(f"{BASE_URL}/api/service-recovery/voucher/{code}/redeem", headers=auth_headers, json={
            "booking_id": "test-booking-123"
        })
        assert resp2.status_code == 200
        assert resp2.json()["ok"] is True
        
        # Verify redeemed
        resp3 = requests.get(f"{BASE_URL}/api/service-recovery/voucher/{code}")
        assert resp3.json()["redeemed"] is True
        assert resp3.json()["valid"] is False
    
    def test_redeem_already_redeemed_400(self, auth_headers):
        """POST /api/service-recovery/voucher/{code}/redeem - 400 if already redeemed"""
        # Issue and redeem
        resp = requests.post(f"{BASE_URL}/api/service-recovery/voucher", headers=auth_headers, json={
            "property_id": PROPERTY_ID,
            "guest_email": f"test_double_{uuid.uuid4().hex[:8]}@test.com",
            "score": 3
        })
        code = resp.json()["voucher"]["code"]
        requests.post(f"{BASE_URL}/api/service-recovery/voucher/{code}/redeem", headers=auth_headers, json={})
        
        # Try redeem again
        resp2 = requests.post(f"{BASE_URL}/api/service-recovery/voucher/{code}/redeem", headers=auth_headers, json={})
        assert resp2.status_code == 400, f"Expected 400 for double redeem, got {resp2.status_code}"
    
    def test_sweep_auto_issues(self, auth_headers):
        """POST /api/service-recovery/sweep - auto-issues for open tickets without voucher"""
        resp = requests.post(f"{BASE_URL}/api/service-recovery/sweep", headers=auth_headers, json={
            "property_id": PROPERTY_ID
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "scanned" in data
        assert "issued" in data


# ============================================================================
# FOLIO SPLIT-BILLING TESTS
# ============================================================================
class TestFolioSplitBilling:
    """Folio Split-Billing endpoints"""
    
    @pytest.fixture(scope="class")
    def test_booking_id(self, auth_headers):
        """Get a booking ID for testing"""
        resp = requests.get(f"{BASE_URL}/api/bookings?property_id={PROPERTY_ID}&limit=1", headers=auth_headers)
        if resp.status_code == 200:
            data = resp.json()
            # Handle both list and dict with items
            if isinstance(data, list) and len(data) > 0:
                return data[0]["id"]
            elif isinstance(data, dict) and data.get("items"):
                return data["items"][0]["id"]
        pytest.skip("No bookings available for folio split testing")
    
    def test_configure_payer(self, auth_headers, test_booking_id):
        """POST /api/folio-split/{booking_id}/configure - adds payer with categories and cap"""
        resp = requests.post(f"{BASE_URL}/api/folio-split/{test_booking_id}/configure", headers=auth_headers, json={
            "payer_name": "TEST_Acme Corp",
            "payer_email": "accounts@acme.test",
            "payer_type": "company",
            "categories": ["room", "tax"],
            "cap_pct": 80
        })
        assert resp.status_code == 200, f"Configure failed: {resp.status_code} - {resp.text}"
        data = resp.json()
        assert data["ok"] is True
        assert data["split"]["payer_name"] == "TEST_Acme Corp"
        assert data["split"]["cap_pct"] == 80
    
    def test_view_allocation(self, auth_headers, test_booking_id):
        """GET /api/folio-split/{booking_id} - returns allocated payers with subtotals"""
        resp = requests.get(f"{BASE_URL}/api/folio-split/{test_booking_id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "booking_id" in data
        assert "payers" in data
        assert "total_charges" in data
        assert "currency" in data
        # Should have at least guest_default payer
        assert len(data["payers"]) >= 1
        for payer in data["payers"]:
            assert "payer_id" in payer
            assert "payer_name" in payer
            assert "subtotal" in payer
            assert "items" in payer
    
    def test_cap_enforcement(self, auth_headers, test_booking_id):
        """Cap enforcement: charges exceeding cap split across boundary"""
        # Configure a payer with a small cap
        resp = requests.post(f"{BASE_URL}/api/folio-split/{test_booking_id}/configure", headers=auth_headers, json={
            "payer_name": "TEST_SmallCap Ltd",
            "payer_type": "company",
            "categories": ["room"],
            "cap_amount": 50  # Small cap
        })
        assert resp.status_code == 200
        
        # View allocation - cap should be enforced
        resp2 = requests.get(f"{BASE_URL}/api/folio-split/{test_booking_id}", headers=auth_headers)
        assert resp2.status_code == 200
        data = resp2.json()
        # Find the capped payer
        capped = next((p for p in data["payers"] if p["payer_name"] == "TEST_SmallCap Ltd"), None)
        if capped:
            assert capped["subtotal"] <= 50.01, f"Cap not enforced: {capped['subtotal']}"
    
    def test_settle_locks_allocation(self, auth_headers, test_booking_id):
        """POST /api/folio-split/{booking_id}/settle - locks the allocation"""
        resp = requests.post(f"{BASE_URL}/api/folio-split/{test_booking_id}/settle", headers=auth_headers, json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "allocation" in data
    
    def test_payer_html_folio(self, auth_headers, test_booking_id):
        """GET /api/folio-split/{booking_id}/payer/{payer_id}/html - returns HTML 200"""
        # Get allocation to find a payer_id
        resp = requests.get(f"{BASE_URL}/api/folio-split/{test_booking_id}", headers=auth_headers)
        payers = resp.json().get("payers", [])
        if not payers:
            pytest.skip("No payers configured")
        payer_id = payers[0]["payer_id"]
        
        # Get HTML folio
        resp2 = requests.get(f"{BASE_URL}/api/folio-split/{test_booking_id}/payer/{payer_id}/html", headers=auth_headers)
        assert resp2.status_code == 200
        assert "text/html" in resp2.headers.get("content-type", "")
        assert "Folio" in resp2.text
    
    def test_booking_not_found_404(self, auth_headers):
        """GET /api/folio-split/{booking_id} - 404 for unknown booking"""
        resp = requests.get(f"{BASE_URL}/api/folio-split/nonexistent-booking-xyz", headers=auth_headers)
        assert resp.status_code == 404


# ============================================================================
# LOYALTY AUTO-TIER TESTS
# ============================================================================
class TestLoyaltyAutoTier:
    """Loyalty Tier Auto-Upgrade endpoints"""
    
    def test_get_config_defaults(self, auth_headers):
        """GET /api/loyalty-auto/{prop}/config - returns DEFAULT_TIERS if not set"""
        resp = requests.get(f"{BASE_URL}/api/loyalty-auto/{PROPERTY_ID}/config", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "tiers" in data
        tiers = data["tiers"]
        assert len(tiers) == 4
        tier_names = [t["tier"] for t in tiers]
        assert "bronze" in tier_names
        assert "silver" in tier_names
        assert "gold" in tier_names
        assert "platinum" in tier_names
    
    def test_save_config_valid_tiers(self, auth_headers):
        """POST /api/loyalty-auto/config - validates tier names"""
        resp = requests.post(f"{BASE_URL}/api/loyalty-auto/config", headers=auth_headers, json={
            "property_id": PROPERTY_ID,
            "tiers": [
                {"tier": "bronze", "min_stays": 0, "min_lifetime": 0},
                {"tier": "silver", "min_stays": 5, "min_lifetime": 2000},
                {"tier": "gold", "min_stays": 10, "min_lifetime": 5000},
                {"tier": "platinum", "min_stays": 25, "min_lifetime": 15000}
            ]
        })
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
    
    def test_save_config_invalid_tier_400(self, auth_headers):
        """POST /api/loyalty-auto/config - rejects invalid tier names"""
        resp = requests.post(f"{BASE_URL}/api/loyalty-auto/config", headers=auth_headers, json={
            "property_id": PROPERTY_ID,
            "tiers": [
                {"tier": "diamond", "min_stays": 50, "min_lifetime": 50000}  # Invalid tier name
            ]
        })
        assert resp.status_code == 400, f"Expected 400 for invalid tier, got {resp.status_code}"
    
    def test_sweep_recomputes_tiers(self, auth_headers):
        """POST /api/loyalty-auto/sweep - recomputes loyalty_tier on guest_profiles"""
        resp = requests.post(f"{BASE_URL}/api/loyalty-auto/sweep", headers=auth_headers, json={
            "property_id": PROPERTY_ID
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "scanned" in data
        assert "upgraded" in data
        assert "downgraded" in data
        assert "unchanged" in data
    
    def test_list_upgrades_log(self, auth_headers):
        """GET /api/loyalty-auto/{prop}/upgrades - lists log with action=upgrade|downgrade"""
        resp = requests.get(f"{BASE_URL}/api/loyalty-auto/{PROPERTY_ID}/upgrades?days=60", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "count" in data
        assert "upgrades" in data
        assert "downgrades" in data
        # Verify log entries have required fields
        for item in data["items"][:5]:
            assert "from_tier" in item
            assert "to_tier" in item
            assert "action" in item
            assert item["action"] in ["upgrade", "downgrade"]


# ============================================================================
# LATE-CHECKOUT OFFER ENGINE TESTS
# ============================================================================
class TestLateCheckoutOfferEngine:
    """Late-Checkout Offer Engine endpoints"""
    
    def test_get_config_defaults(self, auth_headers):
        """GET /api/late-checkout/{prop}/config - returns defaults"""
        resp = requests.get(f"{BASE_URL}/api/late-checkout/{PROPERTY_ID}/config", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "pct_per_hour" in data
        assert "min_charge" in data
        assert "max_hours" in data
        assert "block_if_next_night_booked" in data
    
    def test_save_config(self, auth_headers):
        """POST /api/late-checkout/config - saves pricing config"""
        resp = requests.post(f"{BASE_URL}/api/late-checkout/config", headers=auth_headers, json={
            "property_id": PROPERTY_ID,
            "enabled": True,
            "pct_per_hour": 10.0,
            "min_charge": 15.0,
            "max_hours": 4,
            "block_if_next_night_booked": True
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["config"]["pct_per_hour"] == 10.0
    
    def test_scan_generates_offers(self, auth_headers):
        """POST /api/late-checkout/scan - generates offers for today's checkouts"""
        resp = requests.post(f"{BASE_URL}/api/late-checkout/scan", headers=auth_headers, json={
            "property_id": PROPERTY_ID
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "checkouts_today" in data
        assert "generated" in data
        assert "skipped_blocked" in data
    
    def test_list_offers(self, auth_headers):
        """GET /api/late-checkout/{prop}/offers - returns conversion_pct + revenue"""
        resp = requests.get(f"{BASE_URL}/api/late-checkout/{PROPERTY_ID}/offers?days=7", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "count" in data
        assert "accepted" in data
        assert "revenue" in data
        assert "conversion_pct" in data
    
    def test_accept_offer_posts_folio_charge(self, auth_headers):
        """POST /api/late-checkout/offer/{id}/accept - posts folio_charges row"""
        # First scan to generate offers
        requests.post(f"{BASE_URL}/api/late-checkout/scan", headers=auth_headers, json={
            "property_id": PROPERTY_ID
        })
        
        # Get open offers
        resp = requests.get(f"{BASE_URL}/api/late-checkout/{PROPERTY_ID}/offers?status=open", headers=auth_headers)
        offers = resp.json().get("items", [])
        
        if not offers:
            pytest.skip("No open offers to test accept")
        
        offer = offers[0]
        hours = offer["tiers"][0]["hours"] if offer.get("tiers") else 1
        
        resp2 = requests.post(f"{BASE_URL}/api/late-checkout/offer/{offer['id']}/accept", headers=auth_headers, json={
            "hours": hours
        })
        assert resp2.status_code == 200
        data = resp2.json()
        assert data["ok"] is True
        assert "charged" in data
    
    def test_decline_offer(self, auth_headers):
        """POST /api/late-checkout/offer/{id}/decline - marks declined"""
        # Scan for offers
        requests.post(f"{BASE_URL}/api/late-checkout/scan", headers=auth_headers, json={
            "property_id": PROPERTY_ID
        })
        
        # Get open offers
        resp = requests.get(f"{BASE_URL}/api/late-checkout/{PROPERTY_ID}/offers?status=open", headers=auth_headers)
        offers = resp.json().get("items", [])
        
        if not offers:
            pytest.skip("No open offers to test decline")
        
        offer = offers[0]
        resp2 = requests.post(f"{BASE_URL}/api/late-checkout/offer/{offer['id']}/decline", headers=auth_headers, json={})
        assert resp2.status_code == 200
        assert resp2.json()["ok"] is True


# ============================================================================
# OTA STOP-SELL FORECAST TESTS
# ============================================================================
class TestOTAStopSellForecast:
    """OTA Stop-Sell Forecaster endpoints"""
    
    def test_get_config_defaults(self, auth_headers):
        """GET /api/ota-forecast/{prop}/config - returns defaults"""
        resp = requests.get(f"{BASE_URL}/api/ota-forecast/{PROPERTY_ID}/config", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "commission_pct_default" in data
        assert "horizon_days" in data
        assert "rooms_left_threshold_pct" in data
    
    def test_save_config(self, auth_headers):
        """POST /api/ota-forecast/config - saves commission_pct, horizon_days, threshold"""
        resp = requests.post(f"{BASE_URL}/api/ota-forecast/config", headers=auth_headers, json={
            "property_id": PROPERTY_ID,
            "commission_pct_default": 18.0,
            "horizon_days": 14,
            "rooms_left_threshold_pct": 20.0,
            "channels": ["booking_com", "expedia", "hotels_com"]
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["config"]["commission_pct_default"] == 18.0
    
    def test_forecast_next_14_days(self, auth_headers):
        """GET /api/ota-forecast/{prop} - per-date forecast with recommendations"""
        resp = requests.get(f"{BASE_URL}/api/ota-forecast/{PROPERTY_ID}?days=14", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        
        # May return no_inventory:true if room_types don't have inventory field
        if data.get("no_inventory"):
            pytest.skip("No inventory configured for property - expected behavior")
        
        assert "items" in data
        assert "recommended_count" in data
        assert "avg_last7_pickup_per_day" in data
        
        # Verify per-date structure
        for item in data["items"][:3]:
            assert "date" in item
            assert "rooms_total" in item
            assert "rooms_occupied" in item
            assert "rooms_left" in item
            assert "rooms_left_pct" in item
            assert "forecast_pickup_remaining" in item
            assert "stop_sell_recommended" in item
            assert "estimated_commission_savings" in item
    
    def test_snooze_date(self, auth_headers):
        """POST /api/ota-forecast/{prop}/{date}/snooze - suppresses recommendation"""
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        resp = requests.post(f"{BASE_URL}/api/ota-forecast/{PROPERTY_ID}/{tomorrow}/snooze", headers=auth_headers, json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["date"] == tomorrow
    
    def test_snoozed_date_excluded_from_recommendations(self, auth_headers):
        """Snoozed dates should not be recommended"""
        # Snooze a date
        target_date = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
        requests.post(f"{BASE_URL}/api/ota-forecast/{PROPERTY_ID}/{target_date}/snooze", headers=auth_headers, json={})
        
        # Get forecast
        resp = requests.get(f"{BASE_URL}/api/ota-forecast/{PROPERTY_ID}?days=14", headers=auth_headers)
        if resp.json().get("no_inventory"):
            pytest.skip("No inventory configured")
        
        items = resp.json().get("items", [])
        snoozed_item = next((i for i in items if i["date"] == target_date), None)
        if snoozed_item:
            assert snoozed_item["snoozed"] is True
            # If snoozed, should not be recommended
            if snoozed_item["snoozed"]:
                assert snoozed_item["stop_sell_recommended"] is False


# ============================================================================
# REGRESSION TESTS
# ============================================================================
class TestRegression:
    """Basic regression tests for core functionality"""
    
    def test_auth_login(self):
        """Auth login still works"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert resp.status_code == 200
        assert "token" in resp.json()
    
    def test_bookings_list(self, auth_headers):
        """Bookings list still works"""
        resp = requests.get(f"{BASE_URL}/api/bookings?property_id={PROPERTY_ID}&limit=5", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        # Handle both list and dict with items
        assert isinstance(data, list) or "items" in data
    
    def test_properties_list(self, auth_headers):
        """Properties list still works"""
        resp = requests.get(f"{BASE_URL}/api/properties", headers=auth_headers)
        assert resp.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
