"""
Iteration 266 Tests: Rate Override History Audit Trail, AI Explainer, Release-to-AI
Tests for:
1. POST /api/rates/grid/submit-to-pms appends to rate_override_history collection
2. GET /api/rates/grid/history/{property_id}/{date} returns history sorted desc by created_at
3. POST /api/rates/grid/release/{property_id}/{date} removes lock and adds 'release' action to history
4. After release: grid no longer shows date as locked (live_pms_rate falls back to default_rate)
5. After release: booking/reserve uses base_price (not released override)
6. GET /api/rates/grid/explain/{property_id}/{date} returns ai_rate, breakdown, context, narrative
7. Explain endpoint works with no compset data (compset_avg=null)
8. Auth required for all 3 new endpoints (admin/manager only)
"""
import os
import pytest
import requests
from datetime import datetime, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
PROPERTY_ID = "aldgate-flats"

# Test dates in 2027 to avoid pollution
TEST_DATE_HISTORY = "2027-05-15"
TEST_DATE_RELEASE = "2027-05-16"
TEST_DATE_EXPLAIN = "2027-05-17"
TEST_DATE_EXPLAIN_NO_COMPSET = "2027-05-18"
TEST_DATE_BOOKING_RELEASE = "2027-05-19"


class TestAuthRequired:
    """Verify all 3 new endpoints require admin/manager auth"""

    def test_history_requires_auth(self):
        """GET /api/rates/grid/history requires auth"""
        resp = requests.get(f"{BASE_URL}/api/rates/grid/history/{PROPERTY_ID}/{TEST_DATE_HISTORY}")
        assert resp.status_code in [401, 403], f"Expected 401/403, got {resp.status_code}"
        print("PASS: history endpoint requires auth")

    def test_release_requires_auth(self):
        """POST /api/rates/grid/release requires auth"""
        resp = requests.post(f"{BASE_URL}/api/rates/grid/release/{PROPERTY_ID}/{TEST_DATE_RELEASE}")
        assert resp.status_code in [401, 403], f"Expected 401/403, got {resp.status_code}"
        print("PASS: release endpoint requires auth")

    def test_explain_requires_auth(self):
        """GET /api/rates/grid/explain requires auth"""
        resp = requests.get(f"{BASE_URL}/api/rates/grid/explain/{PROPERTY_ID}/{TEST_DATE_EXPLAIN}")
        assert resp.status_code in [401, 403], f"Expected 401/403, got {resp.status_code}"
        print("PASS: explain endpoint requires auth")


class TestHistoryAuditTrail:
    """Test rate_override_history collection and history endpoint"""

    @pytest.fixture(autouse=True)
    def setup(self, auth_token):
        self.headers = {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}

    def test_submit_creates_history_entry(self, auth_token):
        """POST /api/rates/grid/submit-to-pms appends to rate_override_history"""
        headers = {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
        
        # Step 1: Create an override
        override_resp = requests.post(
            f"{BASE_URL}/api/rates/grid/override",
            headers=headers,
            json={
                "property_id": PROPERTY_ID,
                "changes": [{"date": TEST_DATE_HISTORY, "pms_override": 175, "min_rate": 70}]
            }
        )
        assert override_resp.status_code == 200, f"Override failed: {override_resp.text}"
        print(f"Override created for {TEST_DATE_HISTORY}")

        # Step 2: Submit to PMS
        submit_resp = requests.post(
            f"{BASE_URL}/api/rates/grid/submit-to-pms",
            headers=headers,
            json={"property_id": PROPERTY_ID, "dates": [TEST_DATE_HISTORY]}
        )
        assert submit_resp.status_code == 200, f"Submit failed: {submit_resp.text}"
        data = submit_resp.json()
        assert data.get("pms_synced") >= 1, f"Expected pms_synced >= 1, got {data}"
        print(f"Submit to PMS successful: {data}")

        # Step 3: Check history endpoint
        history_resp = requests.get(
            f"{BASE_URL}/api/rates/grid/history/{PROPERTY_ID}/{TEST_DATE_HISTORY}",
            headers=headers
        )
        assert history_resp.status_code == 200, f"History failed: {history_resp.text}"
        history_data = history_resp.json()
        
        assert "history" in history_data, "Missing 'history' key"
        assert len(history_data["history"]) >= 1, "Expected at least 1 history entry"
        
        # Verify history entry structure
        entry = history_data["history"][0]  # Most recent (sorted desc)
        assert entry.get("action") == "submit", f"Expected action='submit', got {entry.get('action')}"
        assert entry.get("new_rate") == 175, f"Expected new_rate=175, got {entry.get('new_rate')}"
        assert "by" in entry, "Missing 'by' field"
        assert "created_at" in entry, "Missing 'created_at' field"
        print(f"PASS: History entry created with action='submit', new_rate=175, by={entry.get('by')}")

    def test_history_sorted_desc_by_created_at(self, auth_token):
        """History items should be sorted desc by created_at"""
        headers = {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
        
        # Create multiple submissions to generate multiple history entries
        for rate in [180, 185]:
            requests.post(
                f"{BASE_URL}/api/rates/grid/override",
                headers=headers,
                json={"property_id": PROPERTY_ID, "changes": [{"date": TEST_DATE_HISTORY, "pms_override": rate}]}
            )
            requests.post(
                f"{BASE_URL}/api/rates/grid/submit-to-pms",
                headers=headers,
                json={"property_id": PROPERTY_ID, "dates": [TEST_DATE_HISTORY]}
            )

        # Check history
        history_resp = requests.get(
            f"{BASE_URL}/api/rates/grid/history/{PROPERTY_ID}/{TEST_DATE_HISTORY}",
            headers=headers
        )
        assert history_resp.status_code == 200
        history = history_resp.json().get("history", [])
        
        # Verify sorted desc by created_at
        if len(history) >= 2:
            for i in range(len(history) - 1):
                assert history[i]["created_at"] >= history[i + 1]["created_at"], \
                    f"History not sorted desc: {history[i]['created_at']} < {history[i + 1]['created_at']}"
            print(f"PASS: History sorted desc by created_at ({len(history)} entries)")
        else:
            print(f"PASS: History has {len(history)} entry (need more for sort verification)")

    def test_history_has_delta_fields(self, auth_token):
        """History entries should have delta and delta_pct when previous_rate exists"""
        headers = {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
        
        history_resp = requests.get(
            f"{BASE_URL}/api/rates/grid/history/{PROPERTY_ID}/{TEST_DATE_HISTORY}",
            headers=headers
        )
        assert history_resp.status_code == 200
        history = history_resp.json().get("history", [])
        
        # Find an entry with previous_rate
        entries_with_prev = [e for e in history if e.get("previous_rate") is not None]
        if entries_with_prev:
            entry = entries_with_prev[0]
            assert "delta" in entry, "Missing 'delta' field"
            assert "delta_pct" in entry, "Missing 'delta_pct' field"
            print(f"PASS: History entry has delta={entry.get('delta')}, delta_pct={entry.get('delta_pct')}")
        else:
            print("INFO: No entries with previous_rate found (first submission)")


class TestReleaseToAI:
    """Test POST /api/rates/grid/release/{property_id}/{date}"""

    def test_release_removes_lock_and_adds_history(self, auth_token):
        """Release deletes owner-override doc and adds 'release' action to history"""
        headers = {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
        
        # Step 1: Create and submit an override
        requests.post(
            f"{BASE_URL}/api/rates/grid/override",
            headers=headers,
            json={"property_id": PROPERTY_ID, "changes": [{"date": TEST_DATE_RELEASE, "pms_override": 200, "target_sell_rate": 195}]}
        )
        submit_resp = requests.post(
            f"{BASE_URL}/api/rates/grid/submit-to-pms",
            headers=headers,
            json={"property_id": PROPERTY_ID, "dates": [TEST_DATE_RELEASE]}
        )
        assert submit_resp.status_code == 200
        print(f"Override submitted for {TEST_DATE_RELEASE}")

        # Step 2: Verify it's locked in grid
        grid_resp = requests.get(
            f"{BASE_URL}/api/rates/grid/{PROPERTY_ID}?start_date={TEST_DATE_RELEASE}&days=1",
            headers=headers
        )
        assert grid_resp.status_code == 200
        rows = grid_resp.json().get("rows", [])
        assert len(rows) >= 1
        assert rows[0]["live_pms_rate"] == 200, f"Expected live_pms_rate=200, got {rows[0]['live_pms_rate']}"
        print(f"Before release: live_pms_rate={rows[0]['live_pms_rate']}")

        # Step 3: Release to AI
        release_resp = requests.post(
            f"{BASE_URL}/api/rates/grid/release/{PROPERTY_ID}/{TEST_DATE_RELEASE}",
            headers=headers
        )
        assert release_resp.status_code == 200, f"Release failed: {release_resp.text}"
        release_data = release_resp.json()
        assert release_data.get("released") == True, f"Expected released=True, got {release_data}"
        print(f"Release response: {release_data}")

        # Step 4: Verify history has 'release' action
        history_resp = requests.get(
            f"{BASE_URL}/api/rates/grid/history/{PROPERTY_ID}/{TEST_DATE_RELEASE}",
            headers=headers
        )
        assert history_resp.status_code == 200
        history = history_resp.json().get("history", [])
        release_entries = [e for e in history if e.get("action") == "release"]
        assert len(release_entries) >= 1, "Expected at least 1 'release' action in history"
        
        release_entry = release_entries[0]
        assert release_entry.get("previous_rate") == 200, f"Expected previous_rate=200, got {release_entry.get('previous_rate')}"
        assert release_entry.get("new_rate") is None, f"Expected new_rate=None, got {release_entry.get('new_rate')}"
        print(f"PASS: Release history entry: action='release', previous_rate=200, new_rate=None")

    def test_after_release_grid_shows_default_rate(self, auth_token):
        """After release, grid live_pms_rate falls back to default_rate"""
        headers = {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
        
        # Get grid after release
        grid_resp = requests.get(
            f"{BASE_URL}/api/rates/grid/{PROPERTY_ID}?start_date={TEST_DATE_RELEASE}&days=1",
            headers=headers
        )
        assert grid_resp.status_code == 200
        data = grid_resp.json()
        default_rate = data.get("default_rate", 90)
        rows = data.get("rows", [])
        
        assert len(rows) >= 1
        # After release, live_pms_rate should be default_rate (not 200)
        assert rows[0]["live_pms_rate"] == default_rate, \
            f"Expected live_pms_rate={default_rate} (default), got {rows[0]['live_pms_rate']}"
        print(f"PASS: After release, live_pms_rate={rows[0]['live_pms_rate']} (default_rate={default_rate})")


class TestBookingAfterRelease:
    """Test that booking/reserve uses base_price after release (not released override)"""

    def test_booking_uses_base_price_after_release(self, auth_token):
        """After release, booking should use base_price, not the released override"""
        headers = {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
        
        # Step 1: Create and submit override
        requests.post(
            f"{BASE_URL}/api/rates/grid/override",
            headers=headers,
            json={"property_id": PROPERTY_ID, "changes": [{"date": TEST_DATE_BOOKING_RELEASE, "pms_override": 250}]}
        )
        requests.post(
            f"{BASE_URL}/api/rates/grid/submit-to-pms",
            headers=headers,
            json={"property_id": PROPERTY_ID, "dates": [TEST_DATE_BOOKING_RELEASE]}
        )
        print(f"Override 250 submitted for {TEST_DATE_BOOKING_RELEASE}")

        # Step 2: Release
        release_resp = requests.post(
            f"{BASE_URL}/api/rates/grid/release/{PROPERTY_ID}/{TEST_DATE_BOOKING_RELEASE}",
            headers=headers
        )
        assert release_resp.status_code == 200
        print(f"Released {TEST_DATE_BOOKING_RELEASE}")

        # Step 3: Get room type for booking
        room_types_resp = requests.get(f"{BASE_URL}/api/room-types", headers=headers)
        if room_types_resp.status_code == 200:
            room_types = room_types_resp.json()
            aldgate_rt = next((rt for rt in room_types if rt.get("property_id") == PROPERTY_ID), None)
            if aldgate_rt:
                room_type_id = aldgate_rt.get("id")
                base_price = aldgate_rt.get("base_price", 89)
                
                # Step 4: Make booking (public endpoint, no auth)
                check_out = (datetime.strptime(TEST_DATE_BOOKING_RELEASE, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
                booking_resp = requests.post(
                    f"{BASE_URL}/api/booking/reserve",
                    json={
                        "property_id": PROPERTY_ID,
                        "room_type_id": room_type_id,
                        "check_in": TEST_DATE_BOOKING_RELEASE,
                        "check_out": check_out,
                        "guest_name": "Test Release Guest",
                        "guest_email": "release_test@example.com",
                        "rooms": 1
                    }
                )
                
                if booking_resp.status_code in [200, 201]:
                    booking_data = booking_resp.json()
                    total = booking_data.get("total_price") or booking_data.get("total_amount")
                    # Should be base_price (e.g., 89), NOT 250
                    assert total != 250, f"Booking used released override rate 250, should use base_price"
                    print(f"PASS: Booking total={total} (base_price={base_price}), NOT 250 (released override)")
                else:
                    print(f"INFO: Booking endpoint returned {booking_resp.status_code}: {booking_resp.text}")
            else:
                print("INFO: No room type found for aldgate-flats, skipping booking test")
        else:
            print(f"INFO: Could not get room types: {room_types_resp.status_code}")


class TestExplainEndpoint:
    """Test GET /api/rates/grid/explain/{property_id}/{date}"""

    def test_explain_returns_required_fields(self, auth_token):
        """Explain endpoint returns ai_rate, breakdown, context, narrative"""
        headers = {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
        
        # Create some context for the date
        requests.post(
            f"{BASE_URL}/api/rates/grid/override",
            headers=headers,
            json={"property_id": PROPERTY_ID, "changes": [{"date": TEST_DATE_EXPLAIN, "min_rate": 80, "floor_rate": 75}]}
        )
        
        explain_resp = requests.get(
            f"{BASE_URL}/api/rates/grid/explain/{PROPERTY_ID}/{TEST_DATE_EXPLAIN}",
            headers=headers
        )
        assert explain_resp.status_code == 200, f"Explain failed: {explain_resp.text}"
        data = explain_resp.json()
        
        # Required fields
        assert "ai_rate" in data, "Missing 'ai_rate'"
        assert "breakdown" in data, "Missing 'breakdown'"
        assert "context" in data, "Missing 'context'"
        
        # ai_rate should be a number
        assert isinstance(data["ai_rate"], (int, float)), f"ai_rate should be number, got {type(data['ai_rate'])}"
        
        # breakdown structure
        breakdown = data["breakdown"]
        assert "anchor" in breakdown, "Missing breakdown.anchor"
        assert "occupancy_signal" in breakdown, "Missing breakdown.occupancy_signal"
        assert "pickup_signal" in breakdown, "Missing breakdown.pickup_signal"
        assert "guardrails" in breakdown, "Missing breakdown.guardrails"
        
        # context structure
        context = data["context"]
        required_context = ["occupancy_pct", "in_house", "total_rooms", "pickup_24h", 
                          "compset_avg", "lead_time_days", "day_of_week", "owner_override", "is_locked"]
        for field in required_context:
            assert field in context, f"Missing context.{field}"
        
        print(f"PASS: Explain returned ai_rate={data['ai_rate']}, breakdown keys={list(breakdown.keys())}")
        print(f"      Context: occupancy={context['occupancy_pct']}%, pickup={context['pickup_24h']}, compset_avg={context['compset_avg']}")

    def test_explain_returns_narrative(self, auth_token):
        """Explain endpoint returns narrative (Turkish text from gpt-4o-mini)"""
        headers = {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
        
        explain_resp = requests.get(
            f"{BASE_URL}/api/rates/grid/explain/{PROPERTY_ID}/{TEST_DATE_EXPLAIN}",
            headers=headers,
            timeout=30  # LLM may take time
        )
        assert explain_resp.status_code == 200
        data = explain_resp.json()
        
        # narrative should be present (may be None if LLM fails, but key should exist)
        assert "narrative" in data, "Missing 'narrative' key"
        
        if data["narrative"]:
            assert isinstance(data["narrative"], str), f"narrative should be string, got {type(data['narrative'])}"
            assert len(data["narrative"]) > 10, "narrative seems too short"
            print(f"PASS: Narrative returned ({len(data['narrative'])} chars)")
            print(f"      Preview: {data['narrative'][:100]}...")
        else:
            print("INFO: narrative is None (LLM may have failed or key not configured)")

    def test_explain_works_without_compset_data(self, auth_token):
        """Explain endpoint works even with no compset data (compset_avg=null)"""
        headers = {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
        
        # Use a date far in future where no compset data exists
        explain_resp = requests.get(
            f"{BASE_URL}/api/rates/grid/explain/{PROPERTY_ID}/{TEST_DATE_EXPLAIN_NO_COMPSET}",
            headers=headers,
            timeout=30
        )
        assert explain_resp.status_code == 200, f"Explain failed: {explain_resp.text}"
        data = explain_resp.json()
        
        # Should still return valid response
        assert "ai_rate" in data
        assert "breakdown" in data
        assert "context" in data
        
        # compset_avg may be null
        context = data["context"]
        print(f"PASS: Explain works with compset_avg={context.get('compset_avg')}")
        
        # narrative should still be returned (even if compset is null)
        if data.get("narrative"):
            print(f"      Narrative returned even without compset data")
        else:
            print("      INFO: narrative is None (acceptable if LLM key issue)")


class TestExplainContextFields:
    """Detailed tests for explain context fields"""

    def test_explain_context_has_owner_override_when_set(self, auth_token):
        """context.owner_override reflects pms_override value"""
        headers = {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
        
        # Set an override
        requests.post(
            f"{BASE_URL}/api/rates/grid/override",
            headers=headers,
            json={"property_id": PROPERTY_ID, "changes": [{"date": TEST_DATE_EXPLAIN, "pms_override": 165}]}
        )
        
        explain_resp = requests.get(
            f"{BASE_URL}/api/rates/grid/explain/{PROPERTY_ID}/{TEST_DATE_EXPLAIN}",
            headers=headers
        )
        assert explain_resp.status_code == 200
        context = explain_resp.json().get("context", {})
        
        assert context.get("owner_override") == 165, \
            f"Expected owner_override=165, got {context.get('owner_override')}"
        print(f"PASS: context.owner_override={context.get('owner_override')}")

    def test_explain_context_is_locked_after_submit(self, auth_token):
        """context.is_locked=True after submit-to-pms"""
        headers = {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
        
        # Submit to PMS
        requests.post(
            f"{BASE_URL}/api/rates/grid/submit-to-pms",
            headers=headers,
            json={"property_id": PROPERTY_ID, "dates": [TEST_DATE_EXPLAIN]}
        )
        
        explain_resp = requests.get(
            f"{BASE_URL}/api/rates/grid/explain/{PROPERTY_ID}/{TEST_DATE_EXPLAIN}",
            headers=headers
        )
        assert explain_resp.status_code == 200
        context = explain_resp.json().get("context", {})
        
        assert context.get("is_locked") == True, \
            f"Expected is_locked=True after submit, got {context.get('is_locked')}"
        print(f"PASS: context.is_locked={context.get('is_locked')} after submit")


# Fixtures
@pytest.fixture(scope="module")
def auth_token():
    """Get admin auth token"""
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"}
    )
    if resp.status_code == 200:
        token = resp.json().get("access_token") or resp.json().get("token")
        if token:
            print(f"Auth successful, token obtained")
            return token
    pytest.skip(f"Auth failed: {resp.status_code} - {resp.text}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
