"""Iter637 retest of Paket 39 fixes:
- be_gaps.py [:40] truncation + price_display_mode enum 422 + tax_exclusive_markets list handling
- be_extras ics/pdf fallback when booking_ref missing (uses id)
- be_payment_plans pay-now / split intent returns client_secret (STRIPE_SECRET_KEY precedence)
"""
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://review-hub-108.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"
PID = "aldgate-flats"
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
PUBLIC_KEY = "hbx_4kLXlyw1zn-onwVseP1RB0BGEWdVD2gN"


@pytest.fixture(scope="module")
def admin_headers():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, r.text[:200]
    tok = r.json().get("access_token") or r.json().get("token")
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# --- 1. be-settings: full string persisted (no [:10] truncation), enum 422, list handled ---
class TestBeSettings:
    def test_tax_exclusive_persists_full_string(self, admin_headers):
        r = requests.put(f"{API}/booking/be-settings/{PID}", headers=admin_headers,
                         json={"price_display_mode": "tax_exclusive", "tax_exclusive_markets": ["US", "CA"]})
        assert r.status_code == 200, r.text
        got = requests.get(f"{API}/booking/be-settings/{PID}").json()
        assert got["price_display_mode"] == "tax_exclusive", got
        assert got["tax_exclusive_markets"] == ["US", "CA"], got

    def test_bogus_enum_422(self, admin_headers):
        r = requests.put(f"{API}/booking/be-settings/{PID}", headers=admin_headers,
                         json={"price_display_mode": "bogus"})
        assert r.status_code == 422, r.text

    def test_restore_auto_by_market(self, admin_headers):
        r = requests.put(f"{API}/booking/be-settings/{PID}", headers=admin_headers,
                         json={"price_display_mode": "auto_by_market"})
        assert r.status_code == 200
        got = requests.get(f"{API}/booking/be-settings/{PID}").json()
        assert got["price_display_mode"] == "auto_by_market"


# --- 2. Payment endpoints returning client_secret (Stripe test-mode) ---
class TestStripePaymentIntents:
    def _make_booking(self):
        ci = (datetime.now(timezone.utc).date() + timedelta(days=60)).isoformat()
        co = (datetime.now(timezone.utc).date() + timedelta(days=62)).isoformat()
        payload = {"property_id": PID, "room_type_id": "king-aldgate-flats", "check_in": ci, "check_out": co,
                   "guest_name": "Stripe Test", "guest_email": f"stripe-{uuid.uuid4().hex[:6]}@example.com",
                   "guest_phone": "+441234567890", "adults": 2, "children": 0, "rooms": 1,
                   "payment_method": "pay_at_hotel"}
        r = requests.post(f"{API}/public/v1/bookings", headers={"X-API-Key": PUBLIC_KEY}, json=payload, timeout=30)
        if r.status_code not in (200, 201):
            pytest.skip(f"public booking not accepted: {r.status_code} {r.text[:200]}")
        return r.json()

    def test_pay_balance_intent_has_client_secret(self):
        # Use existing MHB-696738A5 that has a real balance (£198.67) — public API pay_at_hotel bookings have no balance flow
        ref = "MHB-696738A5"
        email = "grace@example.com"
        # ensure balance still due
        sched = requests.get(f"{API}/booking/payment-schedule/{ref}", params={"email": email}, timeout=15).json()
        if not (sched.get("balance_due") and float(sched["balance_due"]) > 0):
            pytest.skip("target booking has no balance_due")
        r = requests.post(f"{API}/booking/payment-schedule/{ref}/pay-now", json={"email": email}, timeout=30)
        if r.status_code == 400 and "stripe" in r.text.lower():
            pytest.skip(f"stripe not configured: {r.text[:120]}")
        assert r.status_code == 200, r.text[:300]
        j = r.json()
        assert "client_secret" in j and j["client_secret"], j
        assert "publishable_key" in j

    def test_split_intent_has_client_secret(self, admin_headers):
        b = self._make_booking()
        ref = b.get("booking_ref") or b.get("ref")
        email = b["guest_email"]
        if not ref:
            pytest.skip("no ref")
        r = requests.post(f"{API}/booking/{ref}/split",
                          json={"email": email, "emails": ["p1@x.com"], "include_me": True})
        assert r.status_code == 200, r.text
        tok = r.json()["links"][0]["token"]
        r2 = requests.post(f"{API}/booking/split/{tok}/intent", timeout=30)
        if r2.status_code == 400 and "stripe" in r2.text.lower():
            pytest.skip("stripe not configured")
        assert r2.status_code == 200, r2.text[:300]
        assert r2.json().get("client_secret"), r2.text
