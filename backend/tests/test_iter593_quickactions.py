"""Iter 593 — Calendar Quick Actions: reassign / resend-confirmation / payments checkout."""
import os
import uuid
import pytest
import requests
from datetime import datetime, timedelta, timezone

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE:
    # Fallback: read from frontend/.env
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE = line.split("=", 1)[1].strip().rstrip("/")
                    break
    except Exception:
        pass
assert BASE, "REACT_APP_BACKEND_URL not set"

ADMIN = {"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"}


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    r = sess.post(f"{BASE}/api/auth/login", json=ADMIN, timeout=20)
    assert r.status_code == 200, f"login failed {r.status_code} {r.text[:200]}"
    tok = r.json().get("access_token") or r.json().get("token")
    if tok:
        sess.headers["Authorization"] = f"Bearer {tok}"
    return sess


@pytest.fixture(scope="module")
def property_id(s):
    r = s.get(f"{BASE}/api/properties", timeout=15)
    assert r.status_code == 200
    props = r.json()
    if isinstance(props, dict):
        props = props.get("properties", [])
    pid = "default"
    for p in props:
        if p.get("id") == "default":
            pid = "default"
            break
    return pid


@pytest.fixture(scope="module")
def physical_rooms(s, property_id):
    """Fetch physical rooms via timeline groups."""
    r = s.get(f"{BASE}/api/bookings/timeline/{property_id}", timeout=15)
    assert r.status_code == 200
    tl = r.json()
    rooms = []
    for g in tl.get("groups", []):
        for rm in g.get("rooms", []):
            rooms.append({**rm, "room_type_id": g.get("room_type_id")})
    assert rooms, "no physical rooms"
    return rooms


@pytest.fixture(scope="module")
def seeded_booking(s, property_id, physical_rooms):
    """Create a TEST_ booking with guest_email so we can test resend."""
    ci = (datetime.now(timezone.utc) + timedelta(days=200 + uuid.uuid4().int % 60)).date().isoformat()
    co = (datetime.strptime(ci, "%Y-%m-%d") + timedelta(days=1)).date().isoformat()
    room = physical_rooms[0]
    payload = {
        "property_id": property_id,
        "guest_name": f"TEST_QA_{uuid.uuid4().hex[:6]}",
        "guest_email": f"test_qa_{uuid.uuid4().hex[:6]}@example.com",
        "guest_phone": "+441234567890",
        "check_in": ci,
        "check_out": co,
        "room_id": room["id"],
        "room_number": room.get("name", ""),
        "room_type_id": room.get("room_type_id", ""),
        "total_price": 200.0,
        "currency": "GBP",
        "status": "confirmed",
        "num_guests": 1,
    }
    r = s.post(f"{BASE}/api/bookings", json=payload, timeout=20)
    assert r.status_code in (200, 201), f"create booking failed {r.status_code} {r.text[:300]}"
    b = r.json()
    return b


# ================= RESEND CONFIRMATION =================
class TestResendConfirmation:
    def test_resend_success(self, s, seeded_booking):
        bid = seeded_booking["id"]
        r = s.post(f"{BASE}/api/bookings/{bid}/resend-confirmation", timeout=20)
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        j = r.json()
        assert j.get("ok") is True
        assert j.get("to") == seeded_booking["guest_email"]

    def test_resend_missing_email_422(self, s, property_id, physical_rooms):
        # Create booking without email
        ci = (datetime.now(timezone.utc) + timedelta(days=140)).date().isoformat()
        co = (datetime.now(timezone.utc) + timedelta(days=142)).date().isoformat()
        room = physical_rooms[0]
        payload = {
            "property_id": property_id, "guest_name": f"TEST_QA_NOEMAIL_{uuid.uuid4().hex[:6]}",
            "guest_email": "", "check_in": ci, "check_out": co,
            "room_id": room["id"], "room_number": room.get("name", ""),
            "total_price": 100.0, "currency": "GBP", "status": "confirmed", "num_guests": 1,
        }
        rc = s.post(f"{BASE}/api/bookings", json=payload, timeout=20)
        assert rc.status_code in (200, 201)
        bid = rc.json()["id"]
        r = s.post(f"{BASE}/api/bookings/{bid}/resend-confirmation", timeout=20)
        assert r.status_code == 422, f"expected 422 got {r.status_code} {r.text[:200]}"

    def test_resend_notfound_404(self, s):
        r = s.post(f"{BASE}/api/bookings/nonexistent-{uuid.uuid4().hex}/resend-confirmation", timeout=20)
        assert r.status_code == 404


# ================= REASSIGN ROOM =================
class TestReassignRoom:
    def test_reassign_success(self, s, property_id, seeded_booking, physical_rooms):
        cur_room_id = seeded_booking.get("room_id")
        ci_b = seeded_booking.get("check_in")
        co_b = seeded_booking.get("check_out")
        # Find target room with no conflicting booking in booking date range
        target = None
        for rm in physical_rooms:
            if rm["id"] == cur_room_id:
                continue
            conflict = any(
                bk.get("check_in", "") < co_b and bk.get("check_out", "") > ci_b
                and bk.get("status") not in ("cancelled",)
                for bk in rm.get("bookings", [])
            )
            if not conflict:
                target = rm
                break
        assert target, "need a free second room"
        bid = seeded_booking["id"]
        r = s.put(f"{BASE}/api/bookings/timeline/{property_id}/reassign/{bid}",
                  json={"room_id": target["id"]}, timeout=20)
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        j = r.json()
        assert j.get("status") == "reassigned"
        assert j.get("new_room_id") == target["id"]

        # GET verify persisted — timeline with start=booking.check_in
        ci_b = seeded_booking.get("check_in")
        tl = s.get(f"{BASE}/api/bookings/timeline/{property_id}?start={ci_b}", timeout=15).json()
        found_room = None
        for g in tl.get("groups", []):
            for rm in g.get("rooms", []):
                for bk in rm.get("bookings", []):
                    if bk.get("id") == bid:
                        found_room = rm.get("id")
        assert found_room == target["id"], f"booking not on target room, found={found_room}"

    def test_reassign_missing_room_id(self, s, property_id, seeded_booking):
        bid = seeded_booking["id"]
        r = s.put(f"{BASE}/api/bookings/timeline/{property_id}/reassign/{bid}",
                  json={}, timeout=20)
        # endpoint returns 200 with {"error":...}
        assert r.status_code == 200
        assert "error" in r.json()


# ================= PAYMENTS CHECKOUT =================
class TestPaymentsCheckout:
    def test_checkout_returns_url(self, s, property_id, seeded_booking):
        payload = {
            "amount": 100.0, "currency": "gbp", "property_id": property_id,
            "booking_id": seeded_booking["id"], "description": "TEST_QA checkout",
            "origin_url": BASE,
        }
        r = s.post(f"{BASE}/api/payments/checkout", json=payload, timeout=30)
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        j = r.json()
        assert "checkout_url" in j and j["checkout_url"].startswith("http")
        assert "session_id" in j

    def test_checkout_invalid_amount(self, s, property_id):
        r = s.post(f"{BASE}/api/payments/checkout",
                   json={"amount": 0, "currency": "gbp", "property_id": property_id},
                   timeout=15)
        assert r.status_code == 400
