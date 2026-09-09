"""Iter636 Paket 39: Funnel analytics, ics/pdf confirmation, room reviews, guest account magic-link,
payment plans + split, price display, metasearch feeds."""
import os
import time
import uuid
import pytest
import requests
from datetime import datetime, timedelta, timezone

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://review-hub-108.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"
PID = "aldgate-flats"
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
PUBLIC_KEY = "hbx_4kLXlyw1zn-onwVseP1RB0BGEWdVD2gN"


@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login {r.status_code} {r.text[:200]}"
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ---------------- 1. Funnel ----------------
class TestFunnel:
    def test_invalid_step_422(self):
        r = requests.post(f"{API}/booking/funnel/event", json={"property_id": PID, "session_id": "abcdef12", "step": "bogus"})
        assert r.status_code == 422, r.text

    def test_two_sessions_and_report(self, admin_headers):
        s1 = f"tsess1-{uuid.uuid4().hex[:8]}"
        s2 = f"tsess2-{uuid.uuid4().hex[:8]}"
        # full path session
        for step in ["search", "rooms", "room_view", "rate_select", "details", "payment", "confirm"]:
            r = requests.post(f"{API}/booking/funnel/event", json={"property_id": PID, "session_id": s1, "step": step, "device": "desktop", "source": "google"})
            assert r.status_code == 200
        # partial session
        for step in ["search", "rooms"]:
            r = requests.post(f"{API}/booking/funnel/event", json={"property_id": PID, "session_id": s2, "step": step, "device": "mobile", "source": "direct"})
            assert r.status_code == 200

        rep = requests.get(f"{API}/booking/funnel/{PID}?days=7", headers=admin_headers).json()
        assert rep["sessions"] >= 2
        assert rep["conversions"] >= 1
        assert isinstance(rep["steps"], list) and len(rep["steps"]) == 7
        # drop_pct present
        for step in rep["steps"]:
            assert "drop_pct" in step and "sessions" in step
        assert isinstance(rep["by_device"], list)
        assert isinstance(rep["by_source"], list)
        assert "biggest_drop" in rep


# ---------------- 2. ICS + PDF ----------------
class TestIcsPdf:
    @pytest.fixture(scope="class")
    def existing_booking(self, admin_headers):
        # find a booking with booking_ref via admin bookings endpoint
        r = requests.get(f"{API}/bookings?property_id={PID}&limit=50", headers=admin_headers, timeout=30)
        if r.status_code != 200:
            pytest.skip(f"admin bookings not accessible: {r.status_code}")
        j = r.json()
        items = j if isinstance(j, list) else (j.get("bookings") or j.get("items") or j.get("data") or [])
        for b in items:
            if b.get("booking_ref") and b.get("guest_email") and b.get("check_in"):
                return b
        pytest.skip("no booking with booking_ref+email")

    def test_ics_ok(self, existing_booking):
        b = existing_booking
        r = requests.get(f"{API}/booking/{b['booking_ref']}/calendar.ics", params={"email": b["guest_email"]})
        assert r.status_code == 200, r.text[:200]
        assert "text/calendar" in r.headers.get("content-type", "")
        body = r.text
        assert "BEGIN:VCALENDAR" in body and "DTSTART" in body and "SUMMARY" in body

    def test_pdf_ok(self, existing_booking):
        b = existing_booking
        r = requests.get(f"{API}/booking/{b['booking_ref']}/confirmation.pdf", params={"email": b["guest_email"]})
        assert r.status_code == 200
        assert "application/pdf" in r.headers.get("content-type", "")
        assert r.content[:4] == b"%PDF"
        assert len(r.content) > 1024

    def test_wrong_email_404(self, existing_booking):
        r = requests.get(f"{API}/booking/{existing_booking['booking_ref']}/calendar.ics", params={"email": "wrong@example.com"})
        assert r.status_code == 404


# ---------------- 3. Room reviews ----------------
class TestRoomReviews:
    def test_get_room_reviews(self):
        r = requests.get(f"{API}/booking/room-reviews/{PID}")
        assert r.status_code == 200
        d = r.json()
        assert "property_avg" in d and "rooms" in d
        assert isinstance(d["rooms"], list)

    def test_tag_invalid_room_422(self, admin_headers):
        # find any review id for property
        rv = requests.get(f"{API}/reviews?property_id={PID}", headers=admin_headers)
        if rv.status_code != 200:
            pytest.skip("reviews endpoint not accessible")
        items = rv.json() if isinstance(rv.json(), list) else rv.json().get("items") or rv.json().get("data") or []
        if not items:
            pytest.skip("no reviews")
        rid = items[0].get("id")
        r = requests.put(f"{API}/booking/room-reviews/{rid}/tag", headers=admin_headers, json={"room_type_id": "nonexistent-room-xyz"})
        assert r.status_code == 422

    def test_tag_valid_then_show(self, admin_headers):
        rv = requests.get(f"{API}/reviews?property_id={PID}", headers=admin_headers)
        if rv.status_code != 200:
            pytest.skip("reviews endpoint not accessible")
        items = rv.json() if isinstance(rv.json(), list) else rv.json().get("items") or rv.json().get("data") or []
        if not items:
            pytest.skip("no reviews")
        rid = items[0].get("id")
        r = requests.put(f"{API}/booking/room-reviews/{rid}/tag", headers=admin_headers, json={"room_type_id": "king-aldgate-flats"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["room_type_id"] == "king-aldgate-flats"
        # verify shows up
        out = requests.get(f"{API}/booking/room-reviews/{PID}").json()
        room = next((x for x in out["rooms"] if x["room_type_id"] == "king-aldgate-flats"), None)
        assert room and room["count"] >= 1


# ---------------- 4. Guest account ----------------
class TestGuestAccount:
    def test_magic_link_and_session(self):
        r = requests.post(f"{API}/booking/guest-account/magic-link", json={"email": "grace@example.com", "property_id": PID})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["sent"] in ("mocked", "mock", "queued_mock") or "dev_token" in d
        token = d.get("dev_token")
        if not token:
            pytest.skip("no dev token (live email mode)")
        # use session
        r2 = requests.get(f"{API}/booking/guest-account/session/{token}")
        assert r2.status_code == 200, r2.text
        session_data = r2.json()
        assert "session" in session_data and "profile" in session_data
        prof = session_data["profile"]
        assert prof["email"] == "grace@example.com"
        session = session_data["session"]

        # second use of same token = 401
        r3 = requests.get(f"{API}/booking/guest-account/session/{token}")
        assert r3.status_code == 401

        # /me via session
        r4 = requests.get(f"{API}/booking/guest-account/me", params={"session": session, "property_id": PID})
        assert r4.status_code == 200, r4.text
        assert r4.json()["profile"]["email"] == "grace@example.com"

        # logout
        r5 = requests.post(f"{API}/booking/guest-account/logout", json={"session": session})
        assert r5.status_code == 200
        r6 = requests.get(f"{API}/booking/guest-account/me", params={"session": session})
        assert r6.status_code == 401

    def test_invalid_email_422(self):
        r = requests.post(f"{API}/booking/guest-account/magic-link", json={"email": "not-an-email", "property_id": PID})
        assert r.status_code == 422


# ---------------- 5. Payment plans & split ----------------
class TestPaymentPlans:
    def test_admin_list_schedules(self, admin_headers):
        r = requests.get(f"{API}/booking/payment-schedules/{PID}", headers=admin_headers)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "settings" in d and "items" in d and "counts" in d

    def test_save_settings(self, admin_headers):
        r = requests.put(f"{API}/booking/payment-schedules/{PID}/settings", headers=admin_headers, json={"balance_charge_days_before": 5, "balance_auto_charge_enabled": True, "balance_reminder_days_before": 10, "split_pay_enabled": True})
        assert r.status_code == 200, r.text
        assert r.json()["balance_charge_days_before"] == 5

    def test_run_now(self, admin_headers):
        r = requests.post(f"{API}/booking/payment-schedules/{PID}/run", headers=admin_headers)
        assert r.status_code == 200
        d = r.json()
        assert set(d.keys()) >= {"charged", "failed", "reminded"}

    @pytest.fixture(scope="class")
    def pay_at_hotel_booking(self):
        """Create pay-at-hotel booking via public API."""
        ci = (datetime.now(timezone.utc).date() + timedelta(days=45)).isoformat()
        co = (datetime.now(timezone.utc).date() + timedelta(days=47)).isoformat()
        payload = {
            "property_id": PID,
            "room_type_id": "king-aldgate-flats",
            "check_in": ci,
            "check_out": co,
            "guest_name": "Test SplitPay",
            "guest_email": f"testsplit-{uuid.uuid4().hex[:6]}@example.com",
            "guest_phone": "+441234567890",
            "adults": 2,
            "children": 0,
            "rooms": 1,
            "payment_method": "pay_at_hotel",
        }
        r = requests.post(f"{API}/public/v1/bookings", headers={"X-API-Key": PUBLIC_KEY}, json=payload, timeout=30)
        if r.status_code not in (200, 201):
            pytest.skip(f"public booking create not accepted: {r.status_code} {r.text[:200]}")
        b = r.json()
        return b

    def test_split_flow(self, admin_headers, pay_at_hotel_booking):
        b = pay_at_hotel_booking
        ref = b.get("booking_ref") or b.get("ref")
        email = b.get("guest_email")
        if not ref:
            pytest.skip("no booking_ref returned")

        # split
        r = requests.post(f"{API}/booking/{ref}/split", json={"email": email, "emails": ["p1@x.com", "p2@x.com"], "include_me": True})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["parts"] == 3
        assert len(d["links"]) == 3
        total_amt = sum(x["amount"] for x in d["links"])
        # amounts should sum to total (allow small rounding tolerance)
        total_booking = float(b.get("total_price") or b.get("cart_total") or 0)
        assert abs(total_amt - total_booking) < 1.5, f"sum {total_amt} vs total {total_booking}"

        # duplicate
        r2 = requests.post(f"{API}/booking/{ref}/split", json={"email": email, "emails": ["p3@x.com"], "include_me": True})
        assert r2.status_code == 409

        tokens = [link["token"] for link in d["links"]]

        # get split
        r3 = requests.get(f"{API}/booking/split/{tokens[0]}")
        assert r3.status_code == 200
        assert r3.json().get("booking_ref") == ref

        # mark 1 paid
        r4 = requests.post(f"{API}/booking/split/{tokens[0]}/mark-paid-test", headers=admin_headers)
        assert r4.status_code == 200
        assert r4.json()["booking_payment_status"] in ("partial", "paid")

        # mark all
        for t in tokens[1:]:
            rr = requests.post(f"{API}/booking/split/{t}/mark-paid-test", headers=admin_headers)
            assert rr.status_code == 200
        # final booking status paid
        final = requests.get(f"{API}/booking/payment-schedule/{ref}", params={"email": email}).json()
        assert final.get("payment_status") == "paid"
        # split list
        assert len(final.get("split") or []) == 3


# ---------------- 6. Price display & metasearch ----------------
class TestPriceDisplayMetasearch:
    def test_be_settings_defaults(self):
        r = requests.get(f"{API}/booking/be-settings/{PID}")
        assert r.status_code == 200, r.text
        d = r.json()
        assert "price_display_mode" in d
        assert "total_price_transparency" in d
        assert "tax_exclusive_markets" in d

    def test_set_and_restore_price_display(self, admin_headers):
        # switch to tax_exclusive
        r = requests.put(f"{API}/booking/be-settings/{PID}", headers=admin_headers, json={"price_display_mode": "tax_exclusive"})
        assert r.status_code == 200, r.text
        check = requests.get(f"{API}/booking/be-settings/{PID}").json()
        # BUG: be_gaps.py:59 truncates strings to 10 chars; 'tax_exclusive' → 'tax_exclus'.
        # This breaks price_display_mode enum matching.
        stored = check["price_display_mode"]
        if stored == "tax_exclus":
            pytest.fail(f"BUG be_gaps.py:59 truncates price_display_mode to 10 chars: got '{stored}' instead of 'tax_exclusive'")
        assert stored == "tax_exclusive"
        # restore
        r2 = requests.put(f"{API}/booking/be-settings/{PID}", headers=admin_headers, json={"price_display_mode": "auto_by_market"})
        assert r2.status_code == 200

    @pytest.mark.parametrize("feed", ["trivago", "tripadvisor", "bing"])
    def test_metasearch_feeds(self, feed):
        r = requests.get(f"{API}/hotel-ads/{feed}/{PID}.xml", params={"days": 2})
        assert r.status_code == 200, r.text[:200]
        assert "xml" in r.headers.get("content-type", "").lower()
        assert r.text.startswith("<?xml")

    def test_metasearch_status(self, admin_headers):
        r = requests.get(f"{API}/hotel-ads/metasearch/{PID}", headers=admin_headers)
        assert r.status_code == 200, r.text
        d = r.json()
        assert len(d["feeds"]) == 4
