"""
Iteration 215 - Batch 2 Keyless Features (5 of 30 P0 gaps)
==========================================================
Tests for:
1. Cleaning Checklists per Room Type
2. Room Move / Walk
3. Lost-Found Auto-Match
4. Group Rooming CSV Import
5. Source Attribution
6. Regression smoke tests (tax-presets, walkin, no-show, guest-prefs, late-checkout, service-recovery, room-qr)
"""
import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
PROPERTY_ID = "city-gate"
EMPTY_PROPERTY_ID = "aldgate-flats"

# Test data from main agent context
EXISTING_GROUP_ID = "751a0e98-0015-4b59-a940-74261439eff4"
EXISTING_LOST_FOUND_ITEM_ID = "a102162b-4305-4e11-b3ad-6f509cf5f9e1"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Authentication failed - skipping authenticated tests")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


# ============================================================================
# 1. CLEANING CHECKLISTS PER ROOM TYPE
# ============================================================================
class TestCleaningChecklists:
    """Tests for cleaning checklists feature"""

    def test_list_templates_returns_default_18_items(self, auth_headers):
        """GET /api/cleaning-checklists/{property_id}/templates auto-creates 18-point default"""
        response = requests.get(
            f"{BASE_URL}/api/cleaning-checklists/{PROPERTY_ID}/templates",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "default_items" in data
        assert len(data["default_items"]) == 18, f"Expected 18 default items, got {len(data['default_items'])}"
        # Should have at least one template (the auto-created default)
        assert len(data["items"]) >= 1
        # First template should have 18 items
        first_template = data["items"][0]
        assert len(first_template.get("items", [])) == 18

    def test_upsert_template(self, auth_headers):
        """POST /api/cleaning-checklists/{property_id}/templates upserts template"""
        template_data = {
            "name": "TEST Custom Checklist",
            "room_type_id": "test-room-type",
            "items": [
                {"key": "test_item_1", "label": "Test item 1", "section": "test"},
                {"key": "test_item_2", "label": "Test item 2", "section": "test"},
            ]
        }
        response = requests.post(
            f"{BASE_URL}/api/cleaning-checklists/{PROPERTY_ID}/templates",
            headers=auth_headers,
            json=template_data
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "template" in data
        assert data["template"]["name"] == "TEST Custom Checklist"

    def test_start_run_and_tick_items(self, auth_headers):
        """POST /api/cleaning-checklists/run starts a run, tick toggles items"""
        # First get a room from the property
        room_response = requests.get(
            f"{BASE_URL}/api/room-move/4ef5d34a-ab95-41f9-abdf-e8b6d119451d/options",
            headers=auth_headers
        )
        if room_response.status_code != 200:
            pytest.skip("No rooms available for testing")
        
        rooms = room_response.json().get("options", [])
        if not rooms:
            pytest.skip("No rooms available for testing")
        
        room_id = rooms[0].get("room_id")
        
        # Start a run
        run_response = requests.post(
            f"{BASE_URL}/api/cleaning-checklists/run",
            headers=auth_headers,
            json={"property_id": PROPERTY_ID, "room_id": room_id}
        )
        assert run_response.status_code == 200
        run_data = run_response.json()
        assert "id" in run_data
        assert "items" in run_data
        assert len(run_data["items"]) == 18  # Default template has 18 items
        
        run_id = run_data["id"]
        
        # Tick all 18 items
        for item in run_data["items"]:
            tick_response = requests.post(
                f"{BASE_URL}/api/cleaning-checklists/run/{run_id}/tick",
                headers=auth_headers,
                json={"key": item["key"], "checked": True}
            )
            assert tick_response.status_code == 200
        
        # Complete the run
        complete_response = requests.post(
            f"{BASE_URL}/api/cleaning-checklists/run/{run_id}/complete",
            headers=auth_headers,
            json={}
        )
        assert complete_response.status_code == 200
        complete_data = complete_response.json()
        assert complete_data.get("ok") is True
        assert complete_data.get("score_pct") == 100.0
        assert complete_data.get("auto_flipped_to_clean") is True

    def test_list_runs(self, auth_headers):
        """GET /api/cleaning-checklists/{property_id}/runs returns recent runs"""
        response = requests.get(
            f"{BASE_URL}/api/cleaning-checklists/{PROPERTY_ID}/runs?days=7",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_stats(self, auth_headers):
        """GET /api/cleaning-checklists/{property_id}/stats returns KPIs"""
        response = requests.get(
            f"{BASE_URL}/api/cleaning-checklists/{PROPERTY_ID}/stats?days=30",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "completed" in data
        assert "avg_score_pct" in data
        assert "avg_duration_min" in data
        assert "supervisor_pass_rate" in data
        assert "by_cleaner" in data


# ============================================================================
# 2. ROOM MOVE / WALK
# ============================================================================
class TestRoomMove:
    """Tests for room move/walk feature"""

    def test_get_options_for_booking(self, auth_headers):
        """GET /api/room-move/{booking_id}/options returns eligible target rooms"""
        # Get a confirmed booking
        bookings_response = requests.get(
            f"{BASE_URL}/api/bookings?property_id={PROPERTY_ID}&status=confirmed&limit=1",
            headers=auth_headers
        )
        if bookings_response.status_code != 200 or not bookings_response.json():
            pytest.skip("No confirmed bookings available")
        
        booking_id = bookings_response.json()[0]["id"]
        
        response = requests.get(
            f"{BASE_URL}/api/room-move/{booking_id}/options",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "booking_id" in data
        assert "current_room" in data
        assert "options" in data
        assert "reasons" in data
        # Should have valid reasons
        assert "guest_request" in data["reasons"]
        assert "maintenance" in data["reasons"]
        assert "upgrade" in data["reasons"]

    def test_execute_room_move(self, auth_headers):
        """POST /api/room-move executes move and updates booking"""
        # Get a confirmed booking
        bookings_response = requests.get(
            f"{BASE_URL}/api/bookings?property_id={PROPERTY_ID}&status=confirmed&limit=1",
            headers=auth_headers
        )
        if bookings_response.status_code != 200 or not bookings_response.json():
            pytest.skip("No confirmed bookings available")
        
        booking = bookings_response.json()[0]
        booking_id = booking["id"]
        
        # Get options
        options_response = requests.get(
            f"{BASE_URL}/api/room-move/{booking_id}/options",
            headers=auth_headers
        )
        options = options_response.json().get("options", [])
        if not options:
            pytest.skip("No target rooms available")
        
        target_room = options[0]
        
        # Execute move
        move_response = requests.post(
            f"{BASE_URL}/api/room-move",
            headers=auth_headers,
            json={
                "booking_id": booking_id,
                "new_room_number": target_room["room_number"],
                "new_room_id": target_room.get("room_id"),
                "reason": "guest_request",
                "notes": "TEST move"
            }
        )
        assert move_response.status_code == 200
        data = move_response.json()
        assert data.get("ok") is True
        assert data.get("to") == target_room["room_number"]
        assert "history" in data
        
        # Verify booking was updated via bookings list endpoint
        verify_response = requests.get(
            f"{BASE_URL}/api/bookings?property_id={PROPERTY_ID}&limit=50",
            headers=auth_headers
        )
        assert verify_response.status_code == 200
        bookings = verify_response.json()
        updated_booking = next((b for b in bookings if b["id"] == booking_id), None)
        assert updated_booking is not None
        assert updated_booking.get("room_number") == target_room["room_number"]

    def test_recent_moves(self, auth_headers):
        """GET /api/room-move/{property_id}/recent lists last 14 days of moves"""
        response = requests.get(
            f"{BASE_URL}/api/room-move/{PROPERTY_ID}/recent?days=14",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert "items" in data


# ============================================================================
# 3. LOST-FOUND AUTO-MATCH
# ============================================================================
class TestLostFoundAutoMatch:
    """Tests for lost-found auto-match feature"""

    def test_match_candidates(self, auth_headers):
        """GET /api/lost-found/{item_id}/match-candidates returns scored candidates"""
        response = requests.get(
            f"{BASE_URL}/api/lost-found/{EXISTING_LOST_FOUND_ITEM_ID}/match-candidates",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "item_id" in data
        assert "found_date" in data
        assert "candidates" in data
        
        # Should have candidates with scores
        if data["candidates"]:
            candidate = data["candidates"][0]
            assert "booking_id" in candidate
            assert "guest_name" in candidate
            assert "score" in candidate
            assert "reasons" in candidate
            # Top candidate should have score >= 80 (same room)
            assert candidate["score"] >= 80

    def test_notify_guest_queues_notification(self, auth_headers):
        """POST /api/lost-found/{item_id}/notify-guest queues notification record"""
        # Get candidates first
        candidates_response = requests.get(
            f"{BASE_URL}/api/lost-found/{EXISTING_LOST_FOUND_ITEM_ID}/match-candidates",
            headers=auth_headers
        )
        candidates = candidates_response.json().get("candidates", [])
        if not candidates:
            pytest.skip("No candidates available")
        
        booking_id = candidates[0]["booking_id"]
        
        # Notify guest
        response = requests.post(
            f"{BASE_URL}/api/lost-found/{EXISTING_LOST_FOUND_ITEM_ID}/notify-guest",
            headers=auth_headers,
            json={"booking_id": booking_id, "message": "TEST notification"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "queued_record" in data
        assert data["queued_record"]["status"] == "queued"


# ============================================================================
# 4. GROUP ROOMING CSV IMPORT
# ============================================================================
class TestGroupRoomingImport:
    """Tests for group rooming CSV import feature"""

    def test_preview_csv(self, auth_headers):
        """POST /api/group-rooming/preview parses CSV and returns rows + warnings"""
        csv_text = """guest_name,email,phone,room_type,arrival,departure,rate_override,notes
Jane Doe,jane@test.com,+447700900111,Double,2026-05-01,2026-05-03,,Late arrival
John Smith,john@test.com,,Suite,2026-05-01,2026-05-03,180,VIP"""
        
        response = requests.post(
            f"{BASE_URL}/api/group-rooming/preview",
            headers=auth_headers,
            json={"group_id": EXISTING_GROUP_ID, "csv_text": csv_text}
        )
        assert response.status_code == 200
        data = response.json()
        assert "group_id" in data
        assert "rows" in data
        assert "warnings" in data
        assert "row_count" in data
        assert data["row_count"] == 2
        
        # Check parsed rows
        assert len(data["rows"]) == 2
        assert data["rows"][0]["guest_name"] == "Jane Doe"
        assert data["rows"][1]["guest_name"] == "John Smith"

    def test_commit_creates_bookings(self, auth_headers):
        """POST /api/group-rooming/commit creates child bookings"""
        # First preview
        csv_text = f"""guest_name,email,phone,room_type,arrival,departure,rate_override,notes
TEST Group Guest {uuid.uuid4().hex[:6]},test@test.com,+447700900111,Double,2026-06-01,2026-06-03,,Test booking"""
        
        preview_response = requests.post(
            f"{BASE_URL}/api/group-rooming/preview",
            headers=auth_headers,
            json={"group_id": EXISTING_GROUP_ID, "csv_text": csv_text}
        )
        rows = preview_response.json().get("rows", [])
        
        # Commit
        response = requests.post(
            f"{BASE_URL}/api/group-rooming/commit",
            headers=auth_headers,
            json={"group_id": EXISTING_GROUP_ID, "rows": rows}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data.get("created") == 1
        assert "items" in data
        # Check booking ref format: GRP-XXXXXX-YYYYYY
        assert data["items"][0]["booking_ref"].startswith("GRP-")

    def test_list_group_bookings(self, auth_headers):
        """GET /api/group-rooming/{group_id} lists children"""
        response = requests.get(
            f"{BASE_URL}/api/group-rooming/{EXISTING_GROUP_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "group_id" in data
        assert "count" in data
        assert "items" in data


# ============================================================================
# 5. SOURCE ATTRIBUTION
# ============================================================================
class TestSourceAttribution:
    """Tests for source attribution feature"""

    def test_log_touch_public(self):
        """POST /api/attribution/log (PUBLIC, no auth) writes attribution touch"""
        response = requests.post(
            f"{BASE_URL}/api/attribution/log",
            json={
                "property_id": PROPERTY_ID,
                "session_id": f"test-session-{uuid.uuid4().hex[:8]}",
                "event": "visit",
                "utm_source": "google",
                "utm_medium": "cpc",
                "utm_campaign": "test_campaign",
                "landing_page": "/booking"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "id" in data

    def test_log_multiple_touches_and_booking(self):
        """Log multiple touches with booking_id to test attribution"""
        session_id = f"test-session-{uuid.uuid4().hex[:8]}"
        
        # Touch 1: Visit
        requests.post(f"{BASE_URL}/api/attribution/log", json={
            "property_id": PROPERTY_ID,
            "session_id": session_id,
            "event": "visit",
            "utm_source": "facebook",
            "utm_medium": "social"
        })
        
        # Touch 2: Search
        requests.post(f"{BASE_URL}/api/attribution/log", json={
            "property_id": PROPERTY_ID,
            "session_id": session_id,
            "event": "search",
            "utm_source": "google",
            "utm_medium": "organic"
        })
        
        # Touch 3: Booking (with booking_id)
        response = requests.post(f"{BASE_URL}/api/attribution/log", json={
            "property_id": PROPERTY_ID,
            "session_id": session_id,
            "event": "booking",
            "utm_source": "google",
            "utm_medium": "organic",
            "booking_id": "test-booking-123"
        })
        assert response.status_code == 200

    def test_report_returns_all_models(self, auth_headers):
        """GET /api/attribution/{property_id}/report returns all 4 model breakdowns"""
        response = requests.get(
            f"{BASE_URL}/api/attribution/{PROPERTY_ID}/report?days=30",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check all required fields
        assert "window_days" in data
        assert "total_bookings" in data
        assert "total_sessions" in data
        assert "attributed_sessions" in data
        assert "attributed_revenue" in data
        
        # Check all 4 models present
        assert "first_click" in data
        assert "last_click" in data
        assert "linear" in data
        assert "channel_native" in data
        
        # channel_native should always be populated (from booking.channel)
        assert isinstance(data["channel_native"], list)

    def test_funnel_returns_event_counts(self, auth_headers):
        """GET /api/attribution/{property_id}/funnel returns event counts"""
        response = requests.get(
            f"{BASE_URL}/api/attribution/{PROPERTY_ID}/funnel?days=30",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "window_days" in data
        assert "events" in data
        assert isinstance(data["events"], list)
        
        # Should have at least the 'visit' event we logged
        if data["events"]:
            event = data["events"][0]
            assert "event" in event
            assert "count" in event


# ============================================================================
# 6. REGRESSION SMOKE TESTS (Last 2 batches)
# ============================================================================
class TestRegressionSmoke:
    """Regression tests for features from last 2 batches"""

    def test_tax_presets_list_returns_12_codes(self, auth_headers):
        """Tax presets should return 12 country codes"""
        response = requests.get(
            f"{BASE_URL}/api/tax-presets/",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        # Response format is {"presets": [...]}
        presets = data.get("presets", data) if isinstance(data, dict) else data
        assert len(presets) == 12
        codes = [p["code"] for p in presets]
        assert "GB" in codes
        assert "US-NY" in codes
        assert "TR" in codes

    def test_walkin_availability(self, auth_headers):
        """Walk-in availability endpoint works"""
        today = datetime.now().strftime("%Y-%m-%d")
        response = requests.post(
            f"{BASE_URL}/api/walkin/availability",
            headers=auth_headers,
            json={
                "property_id": PROPERTY_ID,
                "check_in": today,
                "nights": 1,
                "guests": 1
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "offerings" in data

    def test_no_show_policy(self, auth_headers):
        """No-show policy endpoint works"""
        response = requests.get(
            f"{BASE_URL}/api/no-show/{PROPERTY_ID}/policy",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "fee_type" in data

    def test_guest_prefs_upsert(self, auth_headers):
        """Guest prefs upsert endpoint works"""
        guest_id = f"test-guest-{uuid.uuid4().hex[:8]}"
        response = requests.post(
            f"{BASE_URL}/api/guest-prefs/{guest_id}",
            headers=auth_headers,
            json={
                "property_id": PROPERTY_ID,
                "pillow_type": "firm",
                "room_temp_c": 21,
                "dietary": ["vegetarian"]
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True

    def test_late_checkout_quote(self, auth_headers):
        """Late checkout quote endpoint works"""
        # Get a booking first
        bookings_response = requests.get(
            f"{BASE_URL}/api/bookings?property_id={PROPERTY_ID}&limit=1",
            headers=auth_headers
        )
        if not bookings_response.json():
            pytest.skip("No bookings available")
        
        booking_id = bookings_response.json()[0]["id"]
        
        # Correct endpoint: POST /api/late-checkout/quote with booking_id and requested_hour
        response = requests.post(
            f"{BASE_URL}/api/late-checkout/quote",
            headers=auth_headers,
            json={"booking_id": booking_id, "requested_hour": 14}
        )
        assert response.status_code == 200
        data = response.json()
        assert "fee" in data or "quote" in data or "ok" in data or "booking_id" in data

    def test_service_recovery_post(self, auth_headers):
        """Service recovery POST endpoint works"""
        # Correct endpoint: POST /api/service-recovery with text field (not description)
        response = requests.post(
            f"{BASE_URL}/api/service-recovery",
            headers=auth_headers,
            json={
                "property_id": PROPERTY_ID,
                "guest_name": "TEST Guest",
                "category": "room_issue",
                "text": "TEST service recovery issue - room was not cleaned properly",
                "channel": "in_person"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data or data.get("ok") is True

    def test_room_qr_list(self, auth_headers):
        """Room QR list endpoint works"""
        response = requests.get(
            f"{BASE_URL}/api/room-qr/{PROPERTY_ID}/list",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data


# ============================================================================
# CLEANUP
# ============================================================================
@pytest.fixture(scope="module", autouse=True)
def cleanup_test_data(auth_headers):
    """Cleanup test data after all tests"""
    yield
    # Cleanup would go here if needed
    # For now, test data is prefixed with TEST_ for easy identification
