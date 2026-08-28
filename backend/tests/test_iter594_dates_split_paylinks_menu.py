"""Iter 594 — Edit-dates, Split, Payment tracking links, Menu Overrides.

Covers:
- PUT  /api/bookings/{id}/dates            (200 / 422 / 409)
- POST /api/bookings/{id}/split            (200 / 422 / 409)
- POST /api/payments/checkout              (returns tracking checkout_url + stripe_url)
- GET  /api/pay/r/{tx_id}                  (302 -> Stripe, tx becomes 'opened')
- GET  /api/payments/booking-links/{bid}   (returns links)
- GET  /api/bookings/timeline/{pid}        (bars carry pay_link/guest_email/room_id)
- Menu Overrides CRUD                      (get any user; put/delete/reset admin only)
"""
import os
import random
import uuid
import pytest
import requests
from datetime import datetime, timedelta

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE = line.split("=", 1)[1].strip().rstrip("/")
                break
assert BASE, "REACT_APP_BACKEND_URL missing"

ADMIN = {"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"}
PID = "aldgate-flats"


# ---------------- Fixtures ----------------

@pytest.fixture(scope="module")
def admin_sess():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json=ADMIN, timeout=20)
    assert r.status_code == 200, f"login failed {r.status_code} {r.text[:200]}"
    tok = r.json().get("access_token") or r.json().get("token")
    if tok:
        s.headers["Authorization"] = f"Bearer {tok}"
    return s


@pytest.fixture(scope="module")
def rooms(admin_sess):
    r = admin_sess.get(f"{BASE}/api/bookings/timeline/{PID}", timeout=20)
    assert r.status_code == 200
    out = []
    for g in r.json().get("groups", []):
        for rm in g.get("rooms", []):
            out.append({**rm, "room_type_id": g.get("room_type_id")})
    assert len(out) >= 2, "need at least 2 physical rooms"
    return out


def _future_dates(offset_days=250, nights=5):
    ci = (datetime.utcnow() + timedelta(days=offset_days)).date()
    co = ci + timedelta(days=nights)
    return ci.isoformat(), co.isoformat()


@pytest.fixture(scope="module")
def seeded_booking(admin_sess, rooms):
    """Create a fresh TEST_ booking (5 nights) on room[0]."""
    room = rooms[0]
    ci, co = _future_dates(offset_days=random.randint(500, 700), nights=5)
    payload = {
        "property_id": PID,
        "room_type_id": room.get("room_type_id"),
        "room_id": room["id"],
        "room_number": room.get("name", ""),
        "guest_name": "TEST_594 Splitter",
        "guest_email": "test594@example.com",
        "check_in": ci, "check_out": co,
        "adults": 2, "children": 0, "rooms": 1,
        "rate": 100.0, "total_price": 500.0, "currency": "GBP",
        "status": "confirmed", "payment_status": "pending",
        "source": "manual", "channel": "direct",
    }
    r = admin_sess.post(f"{BASE}/api/bookings", json=payload, timeout=20)
    assert r.status_code in (200, 201), f"create booking failed {r.status_code} {r.text[:200]}"
    b = r.json()
    bid = b.get("id") or (b.get("booking") or {}).get("id")
    assert bid
    return {"id": bid, "room": room, "check_in": ci, "check_out": co, "rate": 100.0, "nights": 5}


# ---------------- PUT /bookings/{id}/dates ----------------

class TestEditDates:
    def test_dates_update_ok(self, admin_sess, seeded_booking):
        ci = seeded_booking["check_in"]
        # extend 5 -> 7 nights
        new_co = (datetime.strptime(ci, "%Y-%m-%d").date() + timedelta(days=7)).isoformat()
        r = admin_sess.put(
            f"{BASE}/api/bookings/{seeded_booking['id']}/dates",
            json={"check_in": ci, "check_out": new_co}, timeout=15)
        assert r.status_code == 200, r.text[:200]
        d = r.json()
        assert d["nights"] == 7
        assert d["check_out"] == new_co
        # total = rate * nights (100 * 7)
        assert float(d["total_price"]) == pytest.approx(700.0, abs=0.01)
        # rollback to original for downstream tests
        admin_sess.put(
            f"{BASE}/api/bookings/{seeded_booking['id']}/dates",
            json={"check_in": ci, "check_out": seeded_booking["check_out"]}, timeout=15)

    def test_dates_invalid_range_422(self, admin_sess, seeded_booking):
        ci = seeded_booking["check_in"]
        r = admin_sess.put(
            f"{BASE}/api/bookings/{seeded_booking['id']}/dates",
            json={"check_in": ci, "check_out": ci}, timeout=15)
        assert r.status_code == 422

    def test_dates_conflict_409(self, admin_sess, rooms, seeded_booking):
        # Create an adjacent booking on SAME room, then try to extend seeded booking into it.
        room = seeded_booking["room"]
        ci2 = (datetime.strptime(seeded_booking["check_out"], "%Y-%m-%d").date() + timedelta(days=2)).isoformat()
        co2 = (datetime.strptime(ci2, "%Y-%m-%d").date() + timedelta(days=3)).isoformat()
        payload = {
            "property_id": PID, "room_type_id": room["room_type_id"],
            "room_id": room["id"], "guest_name": "TEST_594 Clash",
            "check_in": ci2, "check_out": co2, "adults": 1, "children": 0, "rooms": 1,
            "rate": 90.0, "total_price": 270.0, "currency": "GBP",
            "status": "confirmed", "payment_status": "pending",
        }
        cr = admin_sess.post(f"{BASE}/api/bookings", json=payload, timeout=20)
        assert cr.status_code in (200, 201), cr.text[:200]
        # Try to extend seeded booking past ci2
        overlap_co = (datetime.strptime(ci2, "%Y-%m-%d").date() + timedelta(days=2)).isoformat()
        r = admin_sess.put(
            f"{BASE}/api/bookings/{seeded_booking['id']}/dates",
            json={"check_in": seeded_booking["check_in"], "check_out": overlap_co}, timeout=15)
        assert r.status_code == 409, f"expected 409 got {r.status_code} {r.text[:200]}"


# ---------------- POST /bookings/{id}/split ----------------

class TestSplitBooking:
    def test_split_ok(self, admin_sess, rooms, seeded_booking):
        # seeded booking: 5 nights, ci..co, rate=100, total=500
        ci_d = datetime.strptime(seeded_booking["check_in"], "%Y-%m-%d").date()
        split_date = (ci_d + timedelta(days=2)).isoformat()
        co = seeded_booking["check_out"]
        # Find a target room free for [split_date, co) — query bookings collection directly via timeline
        tl = admin_sess.get(
            f"{BASE}/api/bookings/timeline/{PID}?start={split_date}&days=10", timeout=20).json()
        target_room = None
        for g in tl.get("groups", []):
            for rm in g.get("rooms", []):
                if rm["id"] == seeded_booking["room"]["id"]:
                    continue
                busy = False
                for bar in rm.get("bookings", []):
                    if bar.get("check_in", "") < co and bar.get("check_out", "") > split_date:
                        busy = True; break
                if not busy:
                    target_room = {**rm, "room_type_id": g.get("room_type_id")}
                    break
            if target_room:
                break
        assert target_room, "no free target room found"
        r = admin_sess.post(
            f"{BASE}/api/bookings/{seeded_booking['id']}/split",
            json={"split_date": split_date, "new_room_id": target_room["id"]},
            timeout=20)
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        d = r.json()
        assert d["first"]["check_out"] == split_date
        assert d["first"]["nights"] == 2
        assert d["second"]["check_in"] == split_date
        assert d["second"]["check_out"] == seeded_booking["check_out"]
        assert d["second"]["room_id"] == target_room["id"]
        # Proportional split of total price (500 * 2/5 = 200, 300)
        assert float(d["first"]["total_price"]) == pytest.approx(200.0, abs=0.01)
        assert float(d["second"]["total_price"]) == pytest.approx(300.0, abs=0.01)
        assert d["second"].get("booking_ref", "").endswith("-B")
        assert d["second"].get("split_from") == seeded_booking["id"]
        # save for next test
        seeded_booking["second_id"] = d["second"]["id"]
        seeded_booking["split_date"] = split_date

    def test_split_out_of_range_422(self, admin_sess, rooms, seeded_booking):
        # Create a small fresh booking to test the out-of-range validation
        room = rooms[0]
        ci, co = _future_dates(offset_days=320, nights=3)
        payload = {
            "property_id": PID, "room_type_id": room["room_type_id"],
            "room_id": room["id"], "guest_name": "TEST_594 OORange",
            "check_in": ci, "check_out": co, "adults": 1, "children": 0, "rooms": 1,
            "rate": 80.0, "total_price": 240.0, "currency": "GBP",
            "status": "confirmed", "payment_status": "pending",
        }
        cr = admin_sess.post(f"{BASE}/api/bookings", json=payload, timeout=20)
        assert cr.status_code in (200, 201)
        bid = cr.json().get("id") or cr.json().get("booking", {}).get("id")
        # split at check_in (boundary) — must be strictly between
        r = admin_sess.post(f"{BASE}/api/bookings/{bid}/split",
                            json={"split_date": ci, "new_room_id": rooms[1]["id"]}, timeout=15)
        assert r.status_code == 422

    def test_split_target_room_conflict_409(self, admin_sess, rooms):
        # Booking A on room[0], booking B on room[1] fully overlapping the intended second half.
        room0, room1 = rooms[0], rooms[1]
        ci_a, co_a = _future_dates(offset_days=380, nights=4)
        pa = {"property_id": PID, "room_type_id": room0["room_type_id"], "room_id": room0["id"],
              "guest_name": "TEST_594 A", "check_in": ci_a, "check_out": co_a,
              "adults": 1, "children": 0, "rooms": 1, "rate": 100.0, "total_price": 400.0,
              "currency": "GBP", "status": "confirmed", "payment_status": "pending"}
        ra = admin_sess.post(f"{BASE}/api/bookings", json=pa, timeout=20); assert ra.status_code in (200, 201)
        bid_a = ra.json().get("id") or ra.json().get("booking", {}).get("id")
        # Blocker on room1 covering last 2 nights of A
        split = (datetime.strptime(ci_a, "%Y-%m-%d").date() + timedelta(days=2)).isoformat()
        pb = {"property_id": PID, "room_type_id": room1["room_type_id"], "room_id": room1["id"],
              "guest_name": "TEST_594 Blocker", "check_in": split, "check_out": co_a,
              "adults": 1, "children": 0, "rooms": 1, "rate": 100.0, "total_price": 200.0,
              "currency": "GBP", "status": "confirmed", "payment_status": "pending"}
        rb = admin_sess.post(f"{BASE}/api/bookings", json=pb, timeout=20); assert rb.status_code in (200, 201)
        # Now split A at 'split' into room1 -> should conflict
        r = admin_sess.post(f"{BASE}/api/bookings/{bid_a}/split",
                            json={"split_date": split, "new_room_id": room1["id"]}, timeout=15)
        assert r.status_code == 409, f"expected 409 got {r.status_code} {r.text[:200]}"


# ---------------- Payments tracking links ----------------

class TestPaymentTracking:
    def test_checkout_returns_tracking_url(self, admin_sess, seeded_booking):
        r = admin_sess.post(f"{BASE}/api/payments/checkout", json={
            "amount": 150.0, "currency": "gbp", "property_id": PID,
            "booking_id": seeded_booking["id"], "kind": "payment",
            "description": "TEST_594 pay-link"
        }, timeout=25)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d.get("tx_id")
        assert "/api/pay/r/" in d.get("checkout_url", ""), d
        assert (d.get("stripe_url") or "").startswith("https://")
        seeded_booking["tx_id"] = d["tx_id"]
        seeded_booking["stripe_url"] = d["stripe_url"]

    def test_pay_redirect_marks_opened(self, admin_sess, seeded_booking):
        tx_id = seeded_booking["tx_id"]
        # Do NOT follow the redirect so we can assert 302
        r = requests.get(f"{BASE}/api/pay/r/{tx_id}", allow_redirects=False, timeout=15)
        assert r.status_code == 302, f"expected 302 got {r.status_code}"
        loc = r.headers.get("location", "")
        assert loc.startswith("https://"), f"redirect url: {loc}"
        # Then verify status via booking-links endpoint
        lr = admin_sess.get(f"{BASE}/api/payments/booking-links/{seeded_booking['id']}", timeout=20)
        assert lr.status_code == 200
        links = lr.json().get("links", [])
        assert any(x.get("id") == tx_id for x in links)
        our = next(x for x in links if x.get("id") == tx_id)
        assert our.get("status") in ("opened", "completed"), our.get("status")

    def test_timeline_has_pay_link_enrichment(self, admin_sess, seeded_booking):
        # Timeline window defaults to 14 days from start; use seeded booking's check_in.
        r = admin_sess.get(
            f"{BASE}/api/bookings/timeline/{PID}?start={seeded_booking['check_in']}&days=14",
            timeout=25)
        assert r.status_code == 200
        bars_with_paylink = []
        for g in r.json().get("groups", []):
            for rm in g.get("rooms", []):
                for bar in rm.get("bookings", []):
                    if bar.get("pay_link"):
                        bars_with_paylink.append(bar)
        assert bars_with_paylink, "no bar carries pay_link enrichment"
        pl = bars_with_paylink[0]["pay_link"]
        assert pl.get("status") in ("opened", "sent", "paid", "initiated", "completed")
        assert isinstance(pl.get("count"), int) and pl["count"] >= 1

    def test_timeline_bar_has_guest_email_and_room_id(self, admin_sess, seeded_booking):
        r = admin_sess.get(
            f"{BASE}/api/bookings/timeline/{PID}?start={seeded_booking['check_in']}&days=14",
            timeout=25)
        assert r.status_code == 200
        found_email = found_room = False
        for g in r.json().get("groups", []):
            for rm in g.get("rooms", []):
                for bar in rm.get("bookings", []):
                    if "guest_email" in bar: found_email = True
                    if "room_id" in bar: found_room = True
        assert found_email and found_room, f"guest_email={found_email} room_id={found_room}"


# ---------------- Menu Overrides ----------------

class TestMenuOverrides:
    MODULE_ID = "test-594-module"

    def test_get_overrides_any_user(self, admin_sess):
        r = admin_sess.get(f"{BASE}/api/menu-overrides", timeout=10)
        assert r.status_code == 200
        assert "overrides" in r.json()

    def test_put_override_admin(self, admin_sess):
        r = admin_sess.put(f"{BASE}/api/menu-overrides/{self.MODULE_ID}",
                           json={"section": "custom-section"}, timeout=10)
        assert r.status_code == 200
        assert r.json().get("override", {}).get("section") == "custom-section"
        # Verify persistence
        g = admin_sess.get(f"{BASE}/api/menu-overrides", timeout=10)
        assert self.MODULE_ID in g.json().get("overrides", {})

    def test_put_override_requires_body(self, admin_sess):
        r = admin_sess.put(f"{BASE}/api/menu-overrides/{self.MODULE_ID}",
                           json={}, timeout=10)
        assert r.status_code == 422

    def test_delete_override(self, admin_sess):
        r = admin_sess.delete(f"{BASE}/api/menu-overrides/{self.MODULE_ID}", timeout=10)
        assert r.status_code == 200
        g = admin_sess.get(f"{BASE}/api/menu-overrides", timeout=10)
        assert self.MODULE_ID not in g.json().get("overrides", {})

    def test_reset_overrides(self, admin_sess):
        # Create two overrides then reset
        admin_sess.put(f"{BASE}/api/menu-overrides/mod-a", json={"hidden": True})
        admin_sess.put(f"{BASE}/api/menu-overrides/mod-b", json={"section": "s"})
        r = admin_sess.post(f"{BASE}/api/menu-overrides/reset", timeout=10)
        assert r.status_code == 200
        g = admin_sess.get(f"{BASE}/api/menu-overrides", timeout=10)
        assert g.json().get("overrides", {}) == {}


# ---------------- Cleanup: reset overrides ----------------

def test_zzz_cleanup_reset(admin_sess):
    """Ensure menu-overrides is reset so subsequent user sessions aren't affected."""
    r = admin_sess.post(f"{BASE}/api/menu-overrides/reset", timeout=10)
    assert r.status_code == 200
