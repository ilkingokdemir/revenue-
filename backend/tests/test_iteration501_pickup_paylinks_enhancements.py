"""Backend tests for iteration 501 enhancements:
- pickup-24h: daily_trend (14 entries) + strong_day + realistic rooms_sold_24h
- morning-brief: pickup_24h block
- dashboard notifications: payment_received notification
- pay-links/send: email send (mocked) + error cases
- Folio integration: folio_items created via _mark_paid earlier simulation
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://review-hub-108.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
BOOKING_ID_WITH_FOLIO = "aa3ba080-435b-4ca4-8b65-134f85899d0f"


@pytest.fixture(scope="module")
def auth_headers():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:200]}"
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok, f"No token in login response"
    return {"Authorization": f"Bearer {tok}"}


# --- Pickup 24h enhancements ---
class TestPickup24hEnhancements:
    def test_daily_trend_14_entries(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/pulse/pickup-24h",
                         params={"property_id": "aldgate-flats"}, headers=auth_headers, timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert "daily_trend" in d, "daily_trend key missing"
        assert isinstance(d["daily_trend"], list)
        assert len(d["daily_trend"]) == 14, f"expected 14 daily_trend entries, got {len(d['daily_trend'])}"
        for e in d["daily_trend"]:
            assert "date" in e and "rooms" in e
            assert isinstance(e["rooms"], int)

    def test_strong_day_boolean(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/pulse/pickup-24h",
                         params={"property_id": "aldgate-flats"}, headers=auth_headers, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "strong_day" in d, "strong_day key missing"
        assert isinstance(d["strong_day"], bool)

    def test_rooms_sold_realistic(self, auth_headers):
        """Upper bound on created_at should limit to real (past-hour) bookings."""
        r = requests.get(f"{BASE_URL}/api/pulse/pickup-24h",
                         params={"property_id": "aldgate-flats"}, headers=auth_headers, timeout=30)
        d = r.json()
        # Iteration ctx says ~2 rooms_sold_24h currently; be lenient — should be small (<50 for demo dataset).
        assert d["rooms_sold_24h"] < 100, f"rooms_sold_24h unrealistically high: {d['rooms_sold_24h']}"


# --- Morning brief pickup block ---
class TestMorningBriefPickup:
    def test_morning_brief_includes_pickup_24h(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/morning-brief/aldgate-flats",
                         headers=auth_headers, timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert "pickup_24h" in d, "morning-brief missing pickup_24h block"
        p = d["pickup_24h"]
        for k in ["rooms", "room_nights", "revenue", "pickup_pct", "strong_day"]:
            assert k in p, f"pickup_24h missing key {k}"


# --- Dashboard notifications: payment_received ---
class TestDashboardNotifications:
    def test_payment_received_notification_present(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/dashboard/notifications/all",
                         headers=auth_headers, timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        notifs = d if isinstance(d, list) else d.get("notifications") or d.get("items") or []
        types = [n.get("type") for n in notifs]
        assert "payment_received" in types, f"payment_received not in notification types: {set(types)}"

    def test_pickup_strong_optional(self, auth_headers):
        """pickup_strong may be absent — absence is OK per iteration_501 spec."""
        r = requests.get(f"{BASE_URL}/api/dashboard/notifications/all",
                         headers=auth_headers, timeout=30)
        assert r.status_code == 200
        # No assertion on presence — just confirms endpoint returns 200.


# --- Pay-links send ---
class TestPayLinksSend:
    def _get_booking_with_email(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/bookings", headers=auth_headers, timeout=30)
        assert r.status_code == 200
        data = r.json()
        arr = data if isinstance(data, list) else data.get("bookings") or data.get("items") or []
        for b in arr:
            if b.get("guest_email"):
                return b
        return None

    def _get_booking_without_email(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/bookings", headers=auth_headers, timeout=30)
        data = r.json()
        arr = data if isinstance(data, list) else data.get("bookings") or data.get("items") or []
        for b in arr:
            if not b.get("guest_email"):
                return b
        return None

    def test_send_link_unknown_booking(self, auth_headers):
        r = requests.post(f"{BASE_URL}/api/pay-links/send",
                          json={"booking_id": "nonexistent-xxx",
                                "checkout_url": "https://checkout.stripe.com/x",
                                "amount": 10.0, "currency": "GBP"},
                          headers=auth_headers, timeout=30)
        assert r.status_code == 404, r.text[:200]

    def test_send_link_no_email_400(self, auth_headers):
        b = self._get_booking_without_email(auth_headers)
        if not b:
            pytest.skip("No booking without guest_email in dataset")
        r = requests.post(f"{BASE_URL}/api/pay-links/send",
                          json={"booking_id": b["id"],
                                "checkout_url": "https://checkout.stripe.com/x",
                                "amount": 10.0, "currency": "GBP"},
                          headers=auth_headers, timeout=30)
        assert r.status_code == 400, r.text[:200]

    def test_send_link_mocked(self, auth_headers):
        b = self._get_booking_with_email(auth_headers)
        assert b, "no booking with guest_email"
        r = requests.post(f"{BASE_URL}/api/pay-links/send",
                          json={"booking_id": b["id"],
                                "checkout_url": "https://checkout.stripe.com/pay/xyz",
                                "amount": 25.5, "currency": "GBP"},
                          headers=auth_headers, timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d.get("status") in ("mocked", "sent"), f"unexpected status: {d}"
        assert d.get("to") == b.get("guest_email")


# --- Folio integration ---
class TestFolioIntegration:
    def test_folio_items_endpoint_alive(self, auth_headers):
        """Ensure the folio-related GET endpoints don't break after _mark_paid inserts."""
        # Try common folio endpoints
        for path in [f"/api/folio/{BOOKING_ID_WITH_FOLIO}",
                     f"/api/folios/{BOOKING_ID_WITH_FOLIO}",
                     f"/api/bookings/{BOOKING_ID_WITH_FOLIO}/folio"]:
            r = requests.get(f"{BASE_URL}{path}", headers=auth_headers, timeout=15)
            # Accept 200, 404 (route may not exist under that name), but NOT 500.
            assert r.status_code != 500, f"{path} returned 500: {r.text[:200]}"

    def test_bookings_get_not_broken(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/bookings", headers=auth_headers, timeout=30)
        assert r.status_code == 200
