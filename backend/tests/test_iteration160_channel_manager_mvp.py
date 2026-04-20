"""
Iteration 160 - Channel Manager MVP Tests
Tests for:
1. Channel Restrictions (MinLOS/MaxLOS/CTA/CTD/StopSell per channel × date)
2. Inbound Reservations (manual entry + iCal URL polling)
3. Parity Monitor (rate drift detection across channels)
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
PROPERTY_ID = "aldgate-flats"

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


@pytest.fixture(scope="module")
def auth_token():
    """Get admin auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.cookies.get("access_token") or response.json().get("access_token")
    pytest.skip(f"Auth failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def auth_session(auth_token):
    """Session with auth cookies"""
    session = requests.Session()
    session.cookies.set("access_token", auth_token)
    session.headers.update({"Content-Type": "application/json"})
    return session


# ==================== CHANNEL RESTRICTIONS TESTS ====================

class TestChannelRestrictionsAuth:
    """Test auth requirements for channel restrictions endpoints"""
    
    def test_list_restrictions_requires_auth(self):
        """GET /api/channel-restrictions/{pid} requires auth"""
        response = requests.get(f"{BASE_URL}/api/channel-restrictions/{PROPERTY_ID}")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: List restrictions requires auth")
    
    def test_bulk_upsert_requires_auth(self):
        """PUT /api/channel-restrictions/{pid}/bulk requires auth"""
        response = requests.put(f"{BASE_URL}/api/channel-restrictions/{PROPERTY_ID}/bulk", json={})
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: Bulk upsert requires auth")
    
    def test_delete_requires_auth(self):
        """DELETE /api/channel-restrictions/{id} requires auth"""
        response = requests.delete(f"{BASE_URL}/api/channel-restrictions/fake-id")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: Delete restriction requires auth")
    
    def test_clear_range_requires_auth(self):
        """POST /api/channel-restrictions/{pid}/clear-range requires auth"""
        response = requests.post(f"{BASE_URL}/api/channel-restrictions/{PROPERTY_ID}/clear-range", json={})
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: Clear range requires auth")


class TestChannelRestrictionsList:
    """Test GET /api/channel-restrictions/{pid}"""
    
    def test_list_restrictions_default_range(self, auth_session):
        """List restrictions with default 30-day range"""
        response = auth_session.get(f"{BASE_URL}/api/channel-restrictions/{PROPERTY_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "dates" in data, "Response should contain dates"
        assert "channels" in data, "Response should contain channels"
        assert "restrictions" in data, "Response should contain restrictions"
        assert "index" in data, "Response should contain index"
        assert "count" in data, "Response should contain count"
        
        # Default range should be ~31 days (today + 30)
        assert len(data["dates"]) >= 30, f"Expected at least 30 dates, got {len(data['dates'])}"
        print(f"PASS: List restrictions returns {len(data['dates'])} dates, {len(data['channels'])} channels, {data['count']} restrictions")
    
    def test_list_restrictions_custom_range(self, auth_session):
        """List restrictions with custom date range"""
        from_date = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")
        to_date = (datetime.now() + timedelta(days=12)).strftime("%Y-%m-%d")
        
        response = auth_session.get(
            f"{BASE_URL}/api/channel-restrictions/{PROPERTY_ID}?from_date={from_date}&to_date={to_date}"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["from_date"] == from_date
        assert data["to_date"] == to_date
        assert len(data["dates"]) == 8, f"Expected 8 dates, got {len(data['dates'])}"
        print(f"PASS: Custom range {from_date} to {to_date} returns {len(data['dates'])} dates")
    
    def test_list_restrictions_filter_by_channel(self, auth_session):
        """List restrictions filtered by channel_id"""
        response = auth_session.get(
            f"{BASE_URL}/api/channel-restrictions/{PROPERTY_ID}?channel_id=booking_com"
        )
        assert response.status_code == 200
        
        data = response.json()
        # All restrictions should be for booking_com
        for r in data["restrictions"]:
            assert r["channel_id"] == "booking_com", f"Expected booking_com, got {r['channel_id']}"
        print(f"PASS: Filter by channel_id returns {len(data['restrictions'])} restrictions for booking_com")


class TestChannelRestrictionsBulkUpsert:
    """Test PUT /api/channel-restrictions/{pid}/bulk"""
    
    def test_bulk_upsert_missing_dates(self, auth_session):
        """Bulk upsert without dates returns 400"""
        response = auth_session.put(
            f"{BASE_URL}/api/channel-restrictions/{PROPERTY_ID}/bulk",
            json={"channel_ids": ["booking_com"]}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("PASS: Bulk upsert without dates returns 400")
    
    def test_bulk_upsert_missing_channels(self, auth_session):
        """Bulk upsert without channel_ids returns 400"""
        from_date = datetime.now().strftime("%Y-%m-%d")
        to_date = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
        
        response = auth_session.put(
            f"{BASE_URL}/api/channel-restrictions/{PROPERTY_ID}/bulk",
            json={"from_date": from_date, "to_date": to_date}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("PASS: Bulk upsert without channel_ids returns 400")
    
    def test_bulk_upsert_invalid_date_range(self, auth_session):
        """Bulk upsert with to_date < from_date returns 400"""
        response = auth_session.put(
            f"{BASE_URL}/api/channel-restrictions/{PROPERTY_ID}/bulk",
            json={
                "from_date": "2026-01-20",
                "to_date": "2026-01-10",
                "channel_ids": ["booking_com"]
            }
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("PASS: Bulk upsert with invalid date range returns 400")
    
    def test_bulk_upsert_min_los(self, auth_session):
        """Bulk upsert with min_los creates restrictions"""
        from_date = (datetime.now() + timedelta(days=60)).strftime("%Y-%m-%d")
        to_date = (datetime.now() + timedelta(days=67)).strftime("%Y-%m-%d")
        
        response = auth_session.put(
            f"{BASE_URL}/api/channel-restrictions/{PROPERTY_ID}/bulk",
            json={
                "from_date": from_date,
                "to_date": to_date,
                "channel_ids": ["booking_com", "expedia"],
                "min_los": 3
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "upserted" in data, "Response should contain upserted count"
        # 8 days × 2 channels = 16 cells
        assert data["upserted"] == 16, f"Expected 16 upserted, got {data['upserted']}"
        print(f"PASS: Bulk upsert min_los=3 created {data['upserted']} restrictions")
    
    def test_bulk_upsert_days_of_week_filter(self, auth_session):
        """Bulk upsert with days_of_week filter only touches specified weekdays"""
        from_date = (datetime.now() + timedelta(days=70)).strftime("%Y-%m-%d")
        to_date = (datetime.now() + timedelta(days=77)).strftime("%Y-%m-%d")
        
        response = auth_session.put(
            f"{BASE_URL}/api/channel-restrictions/{PROPERTY_ID}/bulk",
            json={
                "from_date": from_date,
                "to_date": to_date,
                "channel_ids": ["airbnb"],
                "min_los": 2,
                "days_of_week": [4, 5]  # Friday and Saturday only
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Should only affect Fri/Sat in the 8-day range (typically 2-3 days)
        assert data["upserted"] <= 4, f"Expected <=4 upserted (Fri/Sat only), got {data['upserted']}"
        print(f"PASS: Days of week filter applied, {data['upserted']} restrictions created")
    
    def test_bulk_upsert_null_fields_unchanged(self, auth_session):
        """Null fields in bulk upsert leave existing values unchanged"""
        from_date = (datetime.now() + timedelta(days=80)).strftime("%Y-%m-%d")
        to_date = (datetime.now() + timedelta(days=82)).strftime("%Y-%m-%d")
        
        # First create with min_los=3 and stop_sell=true
        response1 = auth_session.put(
            f"{BASE_URL}/api/channel-restrictions/{PROPERTY_ID}/bulk",
            json={
                "from_date": from_date,
                "to_date": to_date,
                "channel_ids": ["agoda"],
                "min_los": 3,
                "stop_sell": True
            }
        )
        assert response1.status_code == 200
        
        # Now update only max_los (min_los and stop_sell should remain)
        response2 = auth_session.put(
            f"{BASE_URL}/api/channel-restrictions/{PROPERTY_ID}/bulk",
            json={
                "from_date": from_date,
                "to_date": to_date,
                "channel_ids": ["agoda"],
                "max_los": 7
            }
        )
        assert response2.status_code == 200
        
        # Verify the restrictions still have min_los and stop_sell
        response3 = auth_session.get(
            f"{BASE_URL}/api/channel-restrictions/{PROPERTY_ID}?from_date={from_date}&to_date={to_date}&channel_id=agoda"
        )
        assert response3.status_code == 200
        
        data = response3.json()
        for r in data["restrictions"]:
            assert r.get("min_los") == 3, f"min_los should be 3, got {r.get('min_los')}"
            assert r.get("max_los") == 7, f"max_los should be 7, got {r.get('max_los')}"
            assert r.get("stop_sell") == True, f"stop_sell should be True, got {r.get('stop_sell')}"
        print("PASS: Null fields leave existing values unchanged")


class TestChannelRestrictionsDelete:
    """Test DELETE and clear-range endpoints"""
    
    def test_delete_nonexistent_restriction(self, auth_session):
        """DELETE /api/channel-restrictions/{id} with nonexistent ID returns not_found"""
        response = auth_session.delete(f"{BASE_URL}/api/channel-restrictions/nonexistent-id-12345")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "not_found"
        print("PASS: Delete nonexistent restriction returns not_found status")
    
    def test_clear_range(self, auth_session):
        """POST /api/channel-restrictions/{pid}/clear-range deletes restrictions in range"""
        from_date = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
        to_date = (datetime.now() + timedelta(days=95)).strftime("%Y-%m-%d")
        
        # First create some restrictions
        auth_session.put(
            f"{BASE_URL}/api/channel-restrictions/{PROPERTY_ID}/bulk",
            json={
                "from_date": from_date,
                "to_date": to_date,
                "channel_ids": ["booking_com", "expedia"],
                "min_los": 2
            }
        )
        
        # Now clear the range
        response = auth_session.post(
            f"{BASE_URL}/api/channel-restrictions/{PROPERTY_ID}/clear-range",
            json={"from_date": from_date, "to_date": to_date}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "deleted" in data
        assert data["deleted"] >= 0
        print(f"PASS: Clear range deleted {data['deleted']} restrictions")


# ==================== CHANNEL INBOUND TESTS ====================

class TestChannelInboundAuth:
    """Test auth requirements for channel inbound endpoints"""
    
    def test_manual_entry_requires_auth(self):
        """POST /api/channel-inbound/manual requires auth"""
        response = requests.post(f"{BASE_URL}/api/channel-inbound/manual", json={})
        assert response.status_code == 401
        print("PASS: Manual entry requires auth")
    
    def test_list_inbound_requires_auth(self):
        """GET /api/channel-inbound/{pid} requires auth"""
        response = requests.get(f"{BASE_URL}/api/channel-inbound/{PROPERTY_ID}")
        assert response.status_code == 401
        print("PASS: List inbound requires auth")
    
    def test_confirm_requires_auth(self):
        """POST /api/channel-inbound/{id}/confirm requires auth"""
        response = requests.post(f"{BASE_URL}/api/channel-inbound/fake-id/confirm", json={})
        assert response.status_code == 401
        print("PASS: Confirm requires auth")
    
    def test_reject_requires_auth(self):
        """POST /api/channel-inbound/{id}/reject requires auth"""
        response = requests.post(f"{BASE_URL}/api/channel-inbound/fake-id/reject", json={})
        assert response.status_code == 401
        print("PASS: Reject requires auth")
    
    def test_ical_sources_requires_auth(self):
        """GET /api/channel-inbound/ical/sources/{pid} requires auth"""
        response = requests.get(f"{BASE_URL}/api/channel-inbound/ical/sources/{PROPERTY_ID}")
        assert response.status_code == 401
        print("PASS: iCal sources requires auth")


class TestChannelInboundManual:
    """Test manual inbound reservation entry"""
    
    def test_manual_entry_missing_fields(self, auth_session):
        """POST /api/channel-inbound/manual with missing fields returns 400"""
        response = auth_session.post(
            f"{BASE_URL}/api/channel-inbound/manual",
            json={"property_id": PROPERTY_ID, "channel": "Airbnb"}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        assert "Missing" in response.json().get("detail", "")
        print("PASS: Manual entry with missing fields returns 400")
    
    def test_manual_entry_success(self, auth_session):
        """POST /api/channel-inbound/manual creates pending_review row"""
        check_in = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        check_out = (datetime.now() + timedelta(days=33)).strftime("%Y-%m-%d")
        
        response = auth_session.post(
            f"{BASE_URL}/api/channel-inbound/manual",
            json={
                "property_id": PROPERTY_ID,
                "channel": "Airbnb",
                "channel_booking_ref": f"TEST-{datetime.now().timestamp()}",
                "guest_name": "Test Guest Manual",
                "check_in": check_in,
                "check_out": check_out,
                "total_price": 250.00
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["status"] == "pending_review"
        assert data["channel"] == "Airbnb"
        assert data["guest_name"] == "Test Guest Manual"
        assert data["total_price"] == 250.00
        assert "id" in data
        print(f"PASS: Manual entry created with id={data['id']}, status=pending_review")
        return data["id"]


class TestChannelInboundList:
    """Test listing inbound reservations"""
    
    def test_list_inbound_all(self, auth_session):
        """GET /api/channel-inbound/{pid} returns rows with counts"""
        response = auth_session.get(f"{BASE_URL}/api/channel-inbound/{PROPERTY_ID}")
        assert response.status_code == 200
        
        data = response.json()
        assert "rows" in data
        assert "pending_count" in data
        assert "confirmed_count" in data
        assert "total" in data
        print(f"PASS: List inbound returns {data['total']} total, {data['pending_count']} pending, {data['confirmed_count']} confirmed")
    
    def test_list_inbound_filter_status(self, auth_session):
        """GET /api/channel-inbound/{pid}?status= filters correctly"""
        response = auth_session.get(f"{BASE_URL}/api/channel-inbound/{PROPERTY_ID}?status=pending_review")
        assert response.status_code == 200
        
        data = response.json()
        for row in data["rows"]:
            assert row["status"] == "pending_review", f"Expected pending_review, got {row['status']}"
        print(f"PASS: Status filter returns {len(data['rows'])} pending_review rows")


class TestChannelInboundConfirmReject:
    """Test confirm and reject flows"""
    
    def test_confirm_creates_booking(self, auth_session):
        """POST /api/channel-inbound/{id}/confirm promotes to booking"""
        # First create a manual entry
        check_in = (datetime.now() + timedelta(days=40)).strftime("%Y-%m-%d")
        check_out = (datetime.now() + timedelta(days=42)).strftime("%Y-%m-%d")
        
        create_response = auth_session.post(
            f"{BASE_URL}/api/channel-inbound/manual",
            json={
                "property_id": PROPERTY_ID,
                "channel": "Booking.com",
                "channel_booking_ref": f"CONFIRM-TEST-{datetime.now().timestamp()}",
                "guest_name": "Confirm Test Guest",
                "check_in": check_in,
                "check_out": check_out,
                "total_price": 180.00
            }
        )
        assert create_response.status_code == 200
        inbound_id = create_response.json()["id"]
        
        # Now confirm it
        confirm_response = auth_session.post(f"{BASE_URL}/api/channel-inbound/{inbound_id}/confirm")
        assert confirm_response.status_code == 200, f"Expected 200, got {confirm_response.status_code}: {confirm_response.text}"
        
        data = confirm_response.json()
        assert data["status"] == "confirmed"
        assert "booking" in data
        assert data["booking"]["guest_name"] == "Confirm Test Guest"
        assert data["booking"]["total_price"] == 180.00
        assert "id" in data["booking"]
        print(f"PASS: Confirm created booking id={data['booking']['id']}")
        return inbound_id
    
    def test_confirm_twice_returns_409(self, auth_session):
        """POST /api/channel-inbound/{id}/confirm twice returns 409"""
        # Create and confirm
        check_in = (datetime.now() + timedelta(days=50)).strftime("%Y-%m-%d")
        check_out = (datetime.now() + timedelta(days=52)).strftime("%Y-%m-%d")
        
        create_response = auth_session.post(
            f"{BASE_URL}/api/channel-inbound/manual",
            json={
                "property_id": PROPERTY_ID,
                "channel": "Expedia",
                "channel_booking_ref": f"DOUBLE-CONFIRM-{datetime.now().timestamp()}",
                "guest_name": "Double Confirm Guest",
                "check_in": check_in,
                "check_out": check_out,
                "total_price": 200.00
            }
        )
        inbound_id = create_response.json()["id"]
        
        # First confirm
        auth_session.post(f"{BASE_URL}/api/channel-inbound/{inbound_id}/confirm")
        
        # Second confirm should fail
        response = auth_session.post(f"{BASE_URL}/api/channel-inbound/{inbound_id}/confirm")
        assert response.status_code == 409, f"Expected 409, got {response.status_code}"
        print("PASS: Confirm twice returns 409")
    
    def test_reject_with_reason(self, auth_session):
        """POST /api/channel-inbound/{id}/reject sets status=rejected"""
        # Create entry
        check_in = (datetime.now() + timedelta(days=55)).strftime("%Y-%m-%d")
        check_out = (datetime.now() + timedelta(days=57)).strftime("%Y-%m-%d")
        
        create_response = auth_session.post(
            f"{BASE_URL}/api/channel-inbound/manual",
            json={
                "property_id": PROPERTY_ID,
                "channel": "Agoda",
                "channel_booking_ref": f"REJECT-TEST-{datetime.now().timestamp()}",
                "guest_name": "Reject Test Guest",
                "check_in": check_in,
                "check_out": check_out,
                "total_price": 150.00
            }
        )
        inbound_id = create_response.json()["id"]
        
        # Reject it
        response = auth_session.post(
            f"{BASE_URL}/api/channel-inbound/{inbound_id}/reject",
            json={"reason": "Duplicate booking"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "rejected"
        print("PASS: Reject sets status=rejected")


class TestChannelInboundIcal:
    """Test iCal source management"""
    
    def test_add_ical_source_invalid_url(self, auth_session):
        """POST /api/channel-inbound/ical/sources with invalid URL returns 400"""
        response = auth_session.post(
            f"{BASE_URL}/api/channel-inbound/ical/sources",
            json={
                "property_id": PROPERTY_ID,
                "channel": "Airbnb",
                "url": "not-a-valid-url",
                "label": "Test Source"
            }
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("PASS: Invalid iCal URL returns 400")
    
    def test_add_ical_source_success(self, auth_session):
        """POST /api/channel-inbound/ical/sources with valid URL creates source"""
        response = auth_session.post(
            f"{BASE_URL}/api/channel-inbound/ical/sources",
            json={
                "property_id": PROPERTY_ID,
                "channel": "Airbnb",
                "url": "https://example.com/calendar.ics",
                "label": "Test Airbnb Calendar"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "id" in data
        assert data["channel"] == "Airbnb"
        assert data["url"] == "https://example.com/calendar.ics"
        print(f"PASS: iCal source created with id={data['id']}")
        return data["id"]
    
    def test_list_ical_sources(self, auth_session):
        """GET /api/channel-inbound/ical/sources/{pid} returns sources"""
        response = auth_session.get(f"{BASE_URL}/api/channel-inbound/ical/sources/{PROPERTY_ID}")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: List iCal sources returns {len(data)} sources")
    
    def test_delete_ical_source(self, auth_session):
        """DELETE /api/channel-inbound/ical/sources/{id} removes source"""
        # First create a source
        create_response = auth_session.post(
            f"{BASE_URL}/api/channel-inbound/ical/sources",
            json={
                "property_id": PROPERTY_ID,
                "channel": "Vrbo",
                "url": "https://example.com/vrbo-calendar.ics",
                "label": "Test Vrbo Calendar"
            }
        )
        source_id = create_response.json()["id"]
        
        # Delete it
        response = auth_session.delete(f"{BASE_URL}/api/channel-inbound/ical/sources/{source_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "deleted"
        print("PASS: Delete iCal source works")
    
    def test_fetch_ical_unreachable_url(self, auth_session):
        """POST /api/channel-inbound/ical/fetch/{id} with unreachable URL returns 502"""
        # Create source with unreachable URL
        create_response = auth_session.post(
            f"{BASE_URL}/api/channel-inbound/ical/sources",
            json={
                "property_id": PROPERTY_ID,
                "channel": "Airbnb",
                "url": "https://nonexistent-domain-12345.com/calendar.ics",
                "label": "Unreachable Source"
            }
        )
        source_id = create_response.json()["id"]
        
        # Try to fetch - should return 502
        response = auth_session.post(f"{BASE_URL}/api/channel-inbound/ical/fetch/{source_id}")
        assert response.status_code == 502, f"Expected 502, got {response.status_code}"
        print("PASS: Fetch unreachable iCal URL returns 502 (expected behavior)")


# ==================== CHANNEL PARITY TESTS ====================

class TestChannelParityAuth:
    """Test auth requirements for channel parity endpoints"""
    
    def test_parity_requires_auth(self):
        """GET /api/channel-parity/{pid} requires auth"""
        response = requests.get(f"{BASE_URL}/api/channel-parity/{PROPERTY_ID}")
        assert response.status_code == 401
        print("PASS: Parity endpoint requires auth")
    
    def test_parity_config_get_requires_auth(self):
        """GET /api/channel-parity/{pid}/config requires auth"""
        response = requests.get(f"{BASE_URL}/api/channel-parity/{PROPERTY_ID}/config")
        assert response.status_code == 401
        print("PASS: Parity config GET requires auth")
    
    def test_parity_config_put_requires_auth(self):
        """PUT /api/channel-parity/{pid}/config requires auth"""
        response = requests.put(f"{BASE_URL}/api/channel-parity/{PROPERTY_ID}/config", json={})
        assert response.status_code == 401
        print("PASS: Parity config PUT requires auth")


class TestChannelParity:
    """Test parity monitor functionality"""
    
    def test_parity_default_params(self, auth_session):
        """GET /api/channel-parity/{pid} returns parity data with defaults"""
        response = auth_session.get(f"{BASE_URL}/api/channel-parity/{PROPERTY_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "summary" in data
        assert "by_channel" in data
        assert "violations" in data
        assert "baseline" in data
        
        summary = data["summary"]
        assert "total_channels" in summary
        assert "total_violations" in summary
        assert "channels_with_violations" in summary
        assert "overall_parity_pct" in summary
        
        print(f"PASS: Parity returns {summary['total_channels']} channels, {summary['total_violations']} violations, {summary['overall_parity_pct']}% parity")
    
    def test_parity_custom_params(self, auth_session):
        """GET /api/channel-parity/{pid}?days=7&tolerance_pct=10 uses custom params"""
        response = auth_session.get(f"{BASE_URL}/api/channel-parity/{PROPERTY_ID}?days=7&tolerance_pct=10")
        assert response.status_code == 200
        
        data = response.json()
        assert data["days"] == 7
        assert data["tolerance_pct"] == 10.0
        print(f"PASS: Custom params days=7, tolerance=10% applied")
    
    def test_parity_same_rate_channels_no_violations(self, auth_session):
        """With default same-rate channels, violations should be 0"""
        response = auth_session.get(f"{BASE_URL}/api/channel-parity/{PROPERTY_ID}?tolerance_pct=5")
        assert response.status_code == 200
        
        data = response.json()
        # With same-rate rule and no markup, all channels should be in parity
        # Note: This depends on channel_connections having rate_rule="same"
        summary = data["summary"]
        
        # If all channels have same rate rule, parity should be 100%
        if summary["total_channels"] > 0:
            # Check by_channel for rate rules
            same_rate_channels = [c for c in data["by_channel"] if c["rule"] == "same" and c["markup_pct"] == 0]
            for ch in same_rate_channels:
                assert ch["violation_count"] == 0, f"Channel {ch['channel_id']} with same rate should have 0 violations"
        
        print(f"PASS: Same-rate channels have 0 violations, overall parity={summary['overall_parity_pct']}%")


class TestChannelParityConfig:
    """Test parity config endpoints"""
    
    def test_get_config_default(self, auth_session):
        """GET /api/channel-parity/{pid}/config returns default config"""
        response = auth_session.get(f"{BASE_URL}/api/channel-parity/{PROPERTY_ID}/config")
        assert response.status_code == 200
        
        data = response.json()
        assert "property_id" in data
        assert "tolerance_pct" in data
        assert "alert_email" in data
        print(f"PASS: Config returns tolerance_pct={data['tolerance_pct']}")
    
    def test_update_config(self, auth_session):
        """PUT /api/channel-parity/{pid}/config updates config"""
        response = auth_session.put(
            f"{BASE_URL}/api/channel-parity/{PROPERTY_ID}/config",
            json={
                "tolerance_pct": 3.5,
                "alert_email": "revenue@hotel.test",
                "alert_enabled": True
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["tolerance_pct"] == 3.5
        assert data["alert_email"] == "revenue@hotel.test"
        assert data["alert_enabled"] == True
        print("PASS: Config updated successfully")
        
        # Verify by GET
        get_response = auth_session.get(f"{BASE_URL}/api/channel-parity/{PROPERTY_ID}/config")
        get_data = get_response.json()
        assert get_data["tolerance_pct"] == 3.5
        print("PASS: Config persisted correctly")


# ==================== INTEGRATION TEST ====================

class TestChannelManagerIntegration:
    """End-to-end integration test"""
    
    def test_full_inbound_workflow(self, auth_session):
        """Test complete inbound reservation workflow: create → list → confirm → verify booking"""
        # 1. Create manual entry
        check_in = (datetime.now() + timedelta(days=100)).strftime("%Y-%m-%d")
        check_out = (datetime.now() + timedelta(days=103)).strftime("%Y-%m-%d")
        ref = f"INTEGRATION-{datetime.now().timestamp()}"
        
        create_response = auth_session.post(
            f"{BASE_URL}/api/channel-inbound/manual",
            json={
                "property_id": PROPERTY_ID,
                "channel": "Booking.com",
                "channel_booking_ref": ref,
                "guest_name": "Integration Test Guest",
                "check_in": check_in,
                "check_out": check_out,
                "total_price": 450.00
            }
        )
        assert create_response.status_code == 200
        inbound_id = create_response.json()["id"]
        print(f"Step 1: Created inbound reservation {inbound_id}")
        
        # 2. List and verify it appears
        list_response = auth_session.get(f"{BASE_URL}/api/channel-inbound/{PROPERTY_ID}?status=pending_review")
        assert list_response.status_code == 200
        rows = list_response.json()["rows"]
        found = any(r["id"] == inbound_id for r in rows)
        assert found, "Created reservation should appear in pending list"
        print("Step 2: Verified reservation appears in pending list")
        
        # 3. Confirm it
        confirm_response = auth_session.post(f"{BASE_URL}/api/channel-inbound/{inbound_id}/confirm")
        assert confirm_response.status_code == 200
        booking = confirm_response.json()["booking"]
        booking_id = booking["id"]
        print(f"Step 3: Confirmed reservation, created booking {booking_id}")
        
        # 4. Verify it moved to confirmed
        list_confirmed = auth_session.get(f"{BASE_URL}/api/channel-inbound/{PROPERTY_ID}?status=confirmed")
        assert list_confirmed.status_code == 200
        confirmed_rows = list_confirmed.json()["rows"]
        found_confirmed = any(r["id"] == inbound_id for r in confirmed_rows)
        assert found_confirmed, "Confirmed reservation should appear in confirmed list"
        print("Step 4: Verified reservation moved to confirmed list")
        
        # 5. Verify booking exists
        booking_response = auth_session.get(f"{BASE_URL}/api/bookings/{booking_id}")
        assert booking_response.status_code == 200
        booking_data = booking_response.json()
        assert booking_data["guest_name"] == "Integration Test Guest"
        assert booking_data["total_price"] == 450.00
        print("Step 5: Verified booking exists with correct data")
        
        print("PASS: Full inbound workflow completed successfully")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
