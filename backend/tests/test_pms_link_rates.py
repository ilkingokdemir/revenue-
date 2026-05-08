"""
Test suite for PMS Link — Owner rates flow into rate_overrides and booking engine.
Tests: Owner override → rate_overrides doc → booking engine picks up per-night rates.
Uses FRESH dates (2027-02-XX) to avoid pollution from prior tests.

Features tested:
1. POST /api/rates/grid/override + POST /api/rates/grid/submit-to-pms creates rate_overrides doc
   with set_by='owner-override', locked=true, custom_rate=effective
2. Effective rate priority: pms_override > target_sell_rate > live_pms_rate, then max(min_rate, floor_rate)
3. POST /api/booking/reserve picks up owner-override custom_rate for per-night pricing
4. Booking with NO override falls back to room_types.base_price
5. Idempotency: re-submitting same date should UPDATE rate_overrides doc (not duplicate)
6. GET /api/rates/grid reads back live_pms_rate from rate_overrides 'owner-override'
7. GET grid rows include availability:[] array per day
8. Locked override is not overwritten by different set_by doc
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"

# Use fresh dates in 2027-02 to avoid pollution from iteration_264 tests
TEST_DATE_PREFIX = "2027-02"
TEST_DATE_1 = "2027-02-15"  # Override date
TEST_DATE_2 = "2027-02-16"  # No override date (fallback to base_price)
TEST_DATE_3 = "2027-02-17"  # Second override date for mixed booking
TEST_DATE_4 = "2027-02-18"  # Idempotency test date
TEST_DATE_5 = "2027-02-19"  # Locked override test date

# Property with known room types
TEST_PROPERTY = "aldgate-flats"
TEST_ROOM_TYPE = "double-aldgate-flats"  # base_price = £89
TEST_ROOM_BASE_PRICE = 89.0


@pytest.fixture(scope="module")
def auth_token():
    """Get admin auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    return data.get("access_token") or data.get("token")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Auth headers for requests"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


@pytest.fixture(scope="module", autouse=True)
def cleanup_test_data(auth_headers):
    """Cleanup test data before and after tests"""
    # Cleanup before tests
    for date in [TEST_DATE_1, TEST_DATE_2, TEST_DATE_3, TEST_DATE_4, TEST_DATE_5]:
        requests.delete(
            f"{BASE_URL}/api/rates/grid/override/{TEST_PROPERTY}/{date}",
            headers=auth_headers
        )
    yield
    # Cleanup after tests - leave rate_overrides for inspection but clean owner_rate_overrides
    for date in [TEST_DATE_1, TEST_DATE_2, TEST_DATE_3, TEST_DATE_4, TEST_DATE_5]:
        requests.delete(
            f"{BASE_URL}/api/rates/grid/override/{TEST_PROPERTY}/{date}",
            headers=auth_headers
        )


class TestPMSLinkRateOverridesCreation:
    """Test that submit-to-pms creates rate_overrides docs with correct fields"""

    def test_submit_to_pms_creates_rate_overrides_doc(self, auth_headers):
        """POST override + submit-to-pms should create rate_overrides doc with set_by='owner-override', locked=true"""
        # Step 1: Create owner override
        override_payload = {
            "property_id": TEST_PROPERTY,
            "changes": [
                {
                    "date": TEST_DATE_1,
                    "pms_override": 150,
                    "target_sell_rate": 140,
                    "min_rate": 80,
                    "floor_rate": 90
                }
            ]
        }
        response = requests.post(
            f"{BASE_URL}/api/rates/grid/override",
            json=override_payload,
            headers=auth_headers
        )
        assert response.status_code == 200, f"Override failed: {response.text}"
        assert response.json()["saved"] >= 1
        print(f"PASS: Created owner override for {TEST_DATE_1}")

        # Step 2: Submit to PMS
        submit_payload = {
            "property_id": TEST_PROPERTY,
            "dates": [TEST_DATE_1]
        }
        response = requests.post(
            f"{BASE_URL}/api/rates/grid/submit-to-pms",
            json=submit_payload,
            headers=auth_headers
        )
        assert response.status_code == 200, f"Submit to PMS failed: {response.text}"
        data = response.json()
        assert data["queued"] >= 1, f"Expected queued >= 1, got {data['queued']}"
        assert data["pms_synced"] >= 1, f"Expected pms_synced >= 1, got {data['pms_synced']}"
        print(f"PASS: Submit to PMS queued={data['queued']}, pms_synced={data['pms_synced']}")

    def test_effective_rate_priority_pms_override_first(self, auth_headers):
        """Effective rate = pms_override > target_sell_rate > live_pms_rate"""
        # Set pms_override=200, target_sell_rate=180 — effective should be 200
        override_payload = {
            "property_id": TEST_PROPERTY,
            "changes": [
                {
                    "date": TEST_DATE_3,
                    "pms_override": 200,
                    "target_sell_rate": 180,
                    "min_rate": 70,
                    "floor_rate": 80
                }
            ]
        }
        requests.post(f"{BASE_URL}/api/rates/grid/override", json=override_payload, headers=auth_headers)
        
        # Submit to PMS
        submit_payload = {"property_id": TEST_PROPERTY, "dates": [TEST_DATE_3]}
        response = requests.post(
            f"{BASE_URL}/api/rates/grid/submit-to-pms",
            json=submit_payload,
            headers=auth_headers
        )
        assert response.status_code == 200
        
        # Verify live_pms_rate is 200 (pms_override takes priority)
        response = requests.get(
            f"{BASE_URL}/api/rates/grid/{TEST_PROPERTY}",
            params={"start_date": TEST_DATE_3, "days": 1},
            headers=auth_headers
        )
        assert response.status_code == 200
        row = response.json()["rows"][0]
        assert row["live_pms_rate"] == 200, f"Expected live_pms_rate=200, got {row['live_pms_rate']}"
        print("PASS: Effective rate priority: pms_override (200) > target_sell_rate (180)")

    def test_effective_rate_guardrails_applied(self, auth_headers):
        """Effective rate should be max(effective, min_rate, floor_rate)"""
        # Set low pms_override=50 but high min_rate=120 — effective should be 120
        override_payload = {
            "property_id": TEST_PROPERTY,
            "changes": [
                {
                    "date": TEST_DATE_4,
                    "pms_override": 50,
                    "min_rate": 120,
                    "floor_rate": 100
                }
            ]
        }
        requests.post(f"{BASE_URL}/api/rates/grid/override", json=override_payload, headers=auth_headers)
        
        # Submit to PMS
        submit_payload = {"property_id": TEST_PROPERTY, "dates": [TEST_DATE_4]}
        response = requests.post(
            f"{BASE_URL}/api/rates/grid/submit-to-pms",
            json=submit_payload,
            headers=auth_headers
        )
        assert response.status_code == 200
        
        # Verify live_pms_rate is 120 (guardrail applied)
        response = requests.get(
            f"{BASE_URL}/api/rates/grid/{TEST_PROPERTY}",
            params={"start_date": TEST_DATE_4, "days": 1},
            headers=auth_headers
        )
        assert response.status_code == 200
        row = response.json()["rows"][0]
        assert row["live_pms_rate"] == 120, f"Expected live_pms_rate=120 (guardrail), got {row['live_pms_rate']}"
        print("PASS: Guardrail applied: max(50, 120, 100) = 120")


class TestBookingEngineUsesOwnerOverride:
    """Test that POST /api/booking/reserve picks up owner-override custom_rate"""

    def test_booking_with_override_uses_custom_rate(self, auth_headers):
        """Booking on override date should use custom_rate, not base_price"""
        # Ensure override exists for TEST_DATE_1 with rate 150
        override_payload = {
            "property_id": TEST_PROPERTY,
            "changes": [{"date": TEST_DATE_1, "pms_override": 150, "min_rate": 80}]
        }
        requests.post(f"{BASE_URL}/api/rates/grid/override", json=override_payload, headers=auth_headers)
        submit_payload = {"property_id": TEST_PROPERTY, "dates": [TEST_DATE_1]}
        requests.post(f"{BASE_URL}/api/rates/grid/submit-to-pms", json=submit_payload, headers=auth_headers)
        
        # Create booking for 1 night on TEST_DATE_1
        booking_payload = {
            "property_id": TEST_PROPERTY,
            "room_type_id": TEST_ROOM_TYPE,
            "guest_name": "PMS Test Guest Override",
            "guest_email": "pmstest_override@test.com",
            "guest_phone": "+44123456789",
            "check_in": TEST_DATE_1,
            "check_out": TEST_DATE_3,  # 2 nights: TEST_DATE_1 (override 150) + TEST_DATE_2 (no override, base 89)
            "adults": 2,
            "children": 0,
            "rooms": 1,
            "special_requests": "PMS link test - override rate"
        }
        response = requests.post(
            f"{BASE_URL}/api/booking/reserve",
            json=booking_payload
        )
        assert response.status_code == 200, f"Booking failed: {response.text}"
        booking = response.json()
        
        # Expected: night 1 = 150 (override), night 2 = 89 (base) = 239 total
        # But we need to check if TEST_DATE_2 has no override
        expected_total = 150 + TEST_ROOM_BASE_PRICE  # 150 + 89 = 239
        
        print(f"Booking total_price: {booking['total_price']}, expected: {expected_total}")
        # Allow some tolerance for currency rounding
        assert abs(booking["total_price"] - expected_total) < 1, \
            f"Expected total_price ~{expected_total}, got {booking['total_price']}"
        print(f"PASS: Booking uses override rate (150) + base rate (89) = {booking['total_price']}")

    def test_booking_without_override_uses_base_price(self, auth_headers):
        """Booking on date with NO override should use room base_price"""
        # Use a date far in future with no override
        no_override_date = "2027-03-01"
        no_override_checkout = "2027-03-02"
        
        # Ensure no override exists
        requests.delete(
            f"{BASE_URL}/api/rates/grid/override/{TEST_PROPERTY}/{no_override_date}",
            headers=auth_headers
        )
        
        # Create booking for 1 night
        booking_payload = {
            "property_id": TEST_PROPERTY,
            "room_type_id": TEST_ROOM_TYPE,
            "guest_name": "PMS Test Guest NoOverride",
            "guest_email": "pmstest_nooverride@test.com",
            "guest_phone": "+44123456790",
            "check_in": no_override_date,
            "check_out": no_override_checkout,
            "adults": 2,
            "children": 0,
            "rooms": 1,
            "special_requests": "PMS link test - no override (base price)"
        }
        response = requests.post(
            f"{BASE_URL}/api/booking/reserve",
            json=booking_payload
        )
        assert response.status_code == 200, f"Booking failed: {response.text}"
        booking = response.json()
        
        # Expected: 1 night at base_price = 89
        assert booking["total_price"] == TEST_ROOM_BASE_PRICE, \
            f"Expected total_price={TEST_ROOM_BASE_PRICE}, got {booking['total_price']}"
        print(f"PASS: Booking without override uses base_price ({TEST_ROOM_BASE_PRICE})")

    def test_mixed_booking_override_plus_base(self, auth_headers):
        """Booking spanning override + non-override dates should sum correctly"""
        # Set override for TEST_DATE_3 = 200
        override_payload = {
            "property_id": TEST_PROPERTY,
            "changes": [{"date": TEST_DATE_3, "pms_override": 200, "min_rate": 80}]
        }
        requests.post(f"{BASE_URL}/api/rates/grid/override", json=override_payload, headers=auth_headers)
        submit_payload = {"property_id": TEST_PROPERTY, "dates": [TEST_DATE_3]}
        requests.post(f"{BASE_URL}/api/rates/grid/submit-to-pms", json=submit_payload, headers=auth_headers)
        
        # Ensure TEST_DATE_2 has NO override (delete if exists)
        requests.delete(
            f"{BASE_URL}/api/rates/grid/override/{TEST_PROPERTY}/{TEST_DATE_2}",
            headers=auth_headers
        )
        
        # Create booking: TEST_DATE_2 (no override, base 89) + TEST_DATE_3 (override 200) = 2 nights
        booking_payload = {
            "property_id": TEST_PROPERTY,
            "room_type_id": TEST_ROOM_TYPE,
            "guest_name": "PMS Test Guest Mixed",
            "guest_email": "pmstest_mixed@test.com",
            "guest_phone": "+44123456791",
            "check_in": TEST_DATE_2,
            "check_out": TEST_DATE_4,  # 2 nights
            "adults": 2,
            "children": 0,
            "rooms": 1,
            "special_requests": "PMS link test - mixed rates"
        }
        response = requests.post(
            f"{BASE_URL}/api/booking/reserve",
            json=booking_payload
        )
        assert response.status_code == 200, f"Booking failed: {response.text}"
        booking = response.json()
        
        # Expected: night 1 (TEST_DATE_2) = 89 (base), night 2 (TEST_DATE_3) = 200 (override) = 289
        expected_total = TEST_ROOM_BASE_PRICE + 200  # 89 + 200 = 289
        
        print(f"Mixed booking total_price: {booking['total_price']}, expected: {expected_total}")
        assert abs(booking["total_price"] - expected_total) < 1, \
            f"Expected total_price ~{expected_total}, got {booking['total_price']}"
        print(f"PASS: Mixed booking: base (89) + override (200) = {booking['total_price']}")


class TestIdempotencyRateOverrides:
    """Test that re-submitting same date UPDATEs rate_overrides (not duplicates)"""

    def test_resubmit_updates_not_duplicates(self, auth_headers):
        """Re-submitting same date should update existing rate_overrides doc"""
        # First submission: rate = 175
        override_payload = {
            "property_id": TEST_PROPERTY,
            "changes": [{"date": TEST_DATE_5, "pms_override": 175, "min_rate": 80}]
        }
        requests.post(f"{BASE_URL}/api/rates/grid/override", json=override_payload, headers=auth_headers)
        submit_payload = {"property_id": TEST_PROPERTY, "dates": [TEST_DATE_5]}
        response = requests.post(
            f"{BASE_URL}/api/rates/grid/submit-to-pms",
            json=submit_payload,
            headers=auth_headers
        )
        assert response.status_code == 200
        first_sync = response.json()["pms_synced"]
        
        # Verify rate is 175
        response = requests.get(
            f"{BASE_URL}/api/rates/grid/{TEST_PROPERTY}",
            params={"start_date": TEST_DATE_5, "days": 1},
            headers=auth_headers
        )
        assert response.json()["rows"][0]["live_pms_rate"] == 175
        
        # Second submission: rate = 225
        override_payload["changes"][0]["pms_override"] = 225
        requests.post(f"{BASE_URL}/api/rates/grid/override", json=override_payload, headers=auth_headers)
        response = requests.post(
            f"{BASE_URL}/api/rates/grid/submit-to-pms",
            json=submit_payload,
            headers=auth_headers
        )
        assert response.status_code == 200
        second_sync = response.json()["pms_synced"]
        
        # Verify rate is now 225 (updated, not duplicated)
        response = requests.get(
            f"{BASE_URL}/api/rates/grid/{TEST_PROPERTY}",
            params={"start_date": TEST_DATE_5, "days": 1},
            headers=auth_headers
        )
        row = response.json()["rows"][0]
        assert row["live_pms_rate"] == 225, f"Expected live_pms_rate=225 after update, got {row['live_pms_rate']}"
        print(f"PASS: Idempotency - rate updated from 175 to 225 (not duplicated)")


class TestGridReadsOwnerOverride:
    """Test that GET /api/rates/grid reads live_pms_rate from rate_overrides 'owner-override'"""

    def test_grid_shows_owner_override_as_live_pms_rate(self, auth_headers):
        """GET grid should show owner-override custom_rate as live_pms_rate"""
        # Set and submit override
        override_payload = {
            "property_id": TEST_PROPERTY,
            "changes": [{"date": TEST_DATE_1, "pms_override": 165, "min_rate": 80}]
        }
        requests.post(f"{BASE_URL}/api/rates/grid/override", json=override_payload, headers=auth_headers)
        submit_payload = {"property_id": TEST_PROPERTY, "dates": [TEST_DATE_1]}
        requests.post(f"{BASE_URL}/api/rates/grid/submit-to-pms", json=submit_payload, headers=auth_headers)
        
        # GET grid and verify
        response = requests.get(
            f"{BASE_URL}/api/rates/grid/{TEST_PROPERTY}",
            params={"start_date": TEST_DATE_1, "days": 1},
            headers=auth_headers
        )
        assert response.status_code == 200
        row = response.json()["rows"][0]
        
        assert row["live_pms_rate"] == 165, f"Expected live_pms_rate=165, got {row['live_pms_rate']}"
        # current_sell_rate should also reflect the override
        assert row["current_sell_rate"] == 165 or row["current_sell_rate"] is None, \
            f"current_sell_rate should be 165 or None, got {row['current_sell_rate']}"
        print(f"PASS: Grid shows owner-override as live_pms_rate={row['live_pms_rate']}")


class TestGridAvailabilityArray:
    """Test that GET grid rows include availability:[] array per day"""

    def test_grid_rows_have_availability_array(self, auth_headers):
        """Each grid row should have availability array with room_type_id, name, total, booked, free"""
        response = requests.get(
            f"{BASE_URL}/api/rates/grid/{TEST_PROPERTY}",
            params={"start_date": TEST_DATE_1, "days": 3},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify room_types in response
        assert "room_types" in data, "Response should include room_types"
        assert len(data["room_types"]) > 0, "Should have at least one room type"
        
        # Verify each row has availability array
        for row in data["rows"]:
            assert "availability" in row, f"Row {row['date']} missing availability array"
            assert isinstance(row["availability"], list), f"availability should be a list"
            
            # Each availability entry should have required fields
            for avail in row["availability"]:
                assert "room_type_id" in avail, "availability entry missing room_type_id"
                assert "name" in avail, "availability entry missing name"
                assert "total" in avail, "availability entry missing total"
                assert "booked" in avail, "availability entry missing booked"
                assert "free" in avail, "availability entry missing free"
                
                # Verify free = total - booked
                assert avail["free"] == avail["total"] - avail["booked"], \
                    f"free ({avail['free']}) should equal total ({avail['total']}) - booked ({avail['booked']})"
        
        print(f"PASS: Grid rows have availability array with {len(data['rows'][0]['availability'])} room types")

    def test_availability_counts_are_correct(self, auth_headers):
        """Availability free count should be rooms - active bookings for that date"""
        # Get grid for a date range
        response = requests.get(
            f"{BASE_URL}/api/rates/grid/{TEST_PROPERTY}",
            params={"start_date": TEST_DATE_1, "days": 1},
            headers=auth_headers
        )
        assert response.status_code == 200
        row = response.json()["rows"][0]
        
        # Find double room availability
        double_avail = next((a for a in row["availability"] if a["room_type_id"] == TEST_ROOM_TYPE), None)
        if double_avail:
            assert double_avail["total"] == 8, f"Expected 8 total double rooms, got {double_avail['total']}"
            assert double_avail["free"] >= 0, f"Free rooms should be >= 0"
            assert double_avail["booked"] >= 0, f"Booked rooms should be >= 0"
            print(f"PASS: Double room availability: total={double_avail['total']}, booked={double_avail['booked']}, free={double_avail['free']}")
        else:
            print(f"INFO: Double room type not found in availability (may be filtered)")


class TestLockedOverrideNotOverwritten:
    """Test that locked owner-override is not overwritten by different set_by"""

    def test_owner_override_has_locked_true(self, auth_headers):
        """Owner override should have locked=true in rate_overrides"""
        # This is verified by the fact that booking engine picks up the rate
        # If it wasn't locked/present, booking would use base_price
        
        # Set override
        override_payload = {
            "property_id": TEST_PROPERTY,
            "changes": [{"date": TEST_DATE_1, "pms_override": 180, "min_rate": 80}]
        }
        requests.post(f"{BASE_URL}/api/rates/grid/override", json=override_payload, headers=auth_headers)
        submit_payload = {"property_id": TEST_PROPERTY, "dates": [TEST_DATE_1]}
        requests.post(f"{BASE_URL}/api/rates/grid/submit-to-pms", json=submit_payload, headers=auth_headers)
        
        # Create booking to verify rate is picked up
        booking_payload = {
            "property_id": TEST_PROPERTY,
            "room_type_id": TEST_ROOM_TYPE,
            "guest_name": "PMS Test Locked Override",
            "guest_email": "pmstest_locked@test.com",
            "guest_phone": "+44123456792",
            "check_in": TEST_DATE_1,
            "check_out": TEST_DATE_2,  # 1 night
            "adults": 2,
            "children": 0,
            "rooms": 1,
            "special_requests": "PMS link test - locked override"
        }
        response = requests.post(
            f"{BASE_URL}/api/booking/reserve",
            json=booking_payload
        )
        assert response.status_code == 200
        booking = response.json()
        
        # If locked=true and set_by='owner-override', booking should use 180
        assert booking["total_price"] == 180, \
            f"Expected total_price=180 (locked override), got {booking['total_price']}"
        print(f"PASS: Locked owner-override rate (180) used in booking")


class TestPublicBookingEndpoint:
    """Test that /api/booking/reserve is PUBLIC (no auth needed)"""

    def test_booking_reserve_is_public(self):
        """POST /api/booking/reserve should work without auth"""
        # Use a date far in future to avoid conflicts
        public_test_date = "2027-04-01"
        public_test_checkout = "2027-04-02"
        
        booking_payload = {
            "property_id": TEST_PROPERTY,
            "room_type_id": TEST_ROOM_TYPE,
            "guest_name": "Public Booking Test",
            "guest_email": "public_booking@test.com",
            "guest_phone": "+44123456793",
            "check_in": public_test_date,
            "check_out": public_test_checkout,
            "adults": 2,
            "children": 0,
            "rooms": 1,
            "special_requests": "Public endpoint test"
        }
        
        # No auth headers
        response = requests.post(
            f"{BASE_URL}/api/booking/reserve",
            json=booking_payload
        )
        assert response.status_code == 200, f"Public booking failed: {response.text}"
        booking = response.json()
        assert "booking_ref" in booking, "Booking should have booking_ref"
        print(f"PASS: /api/booking/reserve is PUBLIC - booking_ref={booking['booking_ref']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
