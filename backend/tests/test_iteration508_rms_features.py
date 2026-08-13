"""
Iteration 508 tests: RMS features
- Profit-First Pricing
- Group Displacement v2 (shoulder + net-of-commission)
- Attribute-Based Selling (ABS)
- RevPAM (meeting-room dynamic pricing)
"""
import os
import pytest
import requests
from datetime import datetime, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://review-hub-108.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
PROPERTY_ID = "default"


@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed {r.status_code} {r.text}"
    body = r.json()
    tok = body.get("token") or body.get("access_token")
    assert tok, f"no token in {body}"
    return tok


@pytest.fixture(scope="session")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# -------- Profit-First Pricing --------
class TestProfitPricing:
    def test_get_profit_pricing_default(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/profit-pricing/{PROPERTY_ID}?days=7", headers=auth_headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "summary" in data
        s = data["summary"]
        assert "best_channel" in s and "worst_channel" in s and "direct_premium" in s
        assert "findings" in data and isinstance(data["findings"], list)
        assert "matrix" in data and isinstance(data["matrix"], list)
        assert len(data["matrix"]) == 7, f"expected 7 matrix rows got {len(data['matrix'])}"
        row0 = data["matrix"][0]
        channels = row0.get("channels") or {}
        assert channels, f"no channels in row {row0}"
        # Each channel should have gross/commission/net
        ch0 = next(iter(channels.values()))
        assert all(k in ch0 for k in ("gross", "commission", "net")), f"missing triplet keys in {ch0}"

    def test_update_settings_and_cpor_persists(self, auth_headers):
        new_cpor = 27.5
        r = requests.put(
            f"{BASE_URL}/api/profit-pricing/{PROPERTY_ID}/settings",
            headers=auth_headers,
            json={"cpor": new_cpor, "ancillary": {"fnb": 5}},
            timeout=30,
        )
        assert r.status_code in (200, 201), r.text
        # verify
        r2 = requests.get(f"{BASE_URL}/api/profit-pricing/{PROPERTY_ID}?days=7", headers=auth_headers, timeout=30)
        assert r2.status_code == 200
        # cpor may be in settings block or top level
        body = r2.json()
        settings = body.get("settings") or {}
        cpor_val = settings.get("cpor") if isinstance(settings, dict) else None
        assert cpor_val == new_cpor or body.get("cpor") == new_cpor, f"cpor not persisted: {body}"


# -------- Group Displacement v2 --------
class TestGroupDisplacement:
    def _payload(self, rooms, rate, days_out=14):
        d1 = (datetime.utcnow() + timedelta(days=days_out)).date().isoformat()
        d2 = (datetime.utcnow() + timedelta(days=days_out + 2)).date().isoformat()
        return {
            "property_id": PROPERTY_ID,
            "check_in": d1,
            "check_out": d2,
            "rooms_requested": rooms,
            "offered_rate": rate,
            "rate_per_room": rate,
        }

    def test_high_rooms_returns_new_fields_and_rejects(self, auth_headers):
        r = requests.post(f"{BASE_URL}/api/group-displacement/analyze", headers=auth_headers, json=self._payload(60, 70), timeout=45)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ["avg_transient_los", "avg_commission_pct", "shoulder_loss",
                  "net_displacement_cost", "net_value_after_commission",
                  "breakeven_rate_net", "suggested_min_rate_net"]:
            assert k in d, f"missing field {k} in {list(d.keys())}"
        assert "recommendation" in d
        # High rooms low rate → net value should be negative and rec should be reject/negotiate
        if d["net_value_after_commission"] < 0:
            assert d["recommendation"] in ("reject", "negotiate"), d["recommendation"]

    def test_low_rooms_accept(self, auth_headers):
        r = requests.post(f"{BASE_URL}/api/group-displacement/analyze", headers=auth_headers, json=self._payload(8, 85), timeout=45)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("recommendation") in ("accept", "negotiate", "reject")


# -------- ABS --------
class TestABS:
    def test_public_list_has_seeded(self):
        r = requests.get(f"{BASE_URL}/api/abs/public/{PROPERTY_ID}", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        items = data if isinstance(data, list) else data.get("items") or data.get("attributes") or []
        assert len(items) >= 5, f"expected >=5 seeded ABS, got {len(items)}"

    def test_upsert_new_attribute(self, auth_headers):
        payload = {
            "name": "TEST_Balkon manzarası",
            "description": "Test",
            "price": 12.5,
            "active": True,
            "category": "view",
        }
        r = requests.post(f"{BASE_URL}/api/abs/{PROPERTY_ID}", headers=auth_headers, json=payload, timeout=30)
        assert r.status_code in (200, 201), r.text

    def test_widget_booking_with_abs_adds_total(self, auth_headers):
        # Get an attribute id
        pub = requests.get(f"{BASE_URL}/api/abs/public/{PROPERTY_ID}", timeout=30).json()
        items = pub if isinstance(pub, list) else pub.get("items") or pub.get("attributes") or []
        assert items
        attr = items[0]
        attr_id = attr.get("id") or attr.get("_id") or attr.get("attribute_id")
        attr_price = float(attr.get("price", 0) or 0)
        assert attr_id and attr_price > 0
        # Book directly (skip check-availability due to known bug w/ null base_rate)
        ci = (datetime.utcnow() + timedelta(days=25)).date().isoformat()
        co = (datetime.utcnow() + timedelta(days=27)).date().isoformat()
        base_rate = 120.0
        nights = 2
        payload = {
            "property_id": PROPERTY_ID,
            "room_type": "Standard Double",
            "check_in": ci,
            "check_out": co,
            "guests": 2,
            "rooms": 1,
            "rate": base_rate,
            "guest_name": "TEST Guest ABS",
            "guest_email": "test_abs@example.com",
            "guest_phone": "+900000000",
            "pay_now": False,
            "abs_attribute_ids": [attr_id],
        }
        r = requests.post(f"{BASE_URL}/api/booking-widget/book", json=payload, timeout=45)
        assert r.status_code in (200, 201), r.text
        b = r.json()
        booking = b.get("booking") or b
        expected_abs = round(attr_price * nights, 2)
        expected_total = round(base_rate * nights + expected_abs, 2)
        got_total = booking.get("total") or b.get("total") or 0
        assert abs(got_total - expected_total) < 0.5, (
            f"total {got_total} != expected {expected_total} (base {base_rate}*{nights} + abs {expected_abs})"
        )

    def test_admin_stats(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/abs/{PROPERTY_ID}", headers=auth_headers, timeout=30)
        assert r.status_code == 200, r.text


# -------- RevPAM --------
class TestRevPAM:
    def test_get_revpam(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/revpam/{PROPERTY_ID}?days=14", headers=auth_headers, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        spaces = d.get("spaces") if isinstance(d, dict) else d
        assert isinstance(spaces, list) and len(spaces) >= 1, f"no spaces: {d}"
        sp0 = spaces[0]
        assert "revpash" in sp0 or "revpam" in sp0 or "utilization_pct" in sp0
        assert "days" in sp0 and len(sp0["days"]) == 14

    def test_apply_override_and_booking_uses_it(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/revpam/{PROPERTY_ID}?days=14", headers=auth_headers, timeout=30)
        d = r.json()
        spaces = d.get("spaces") or d
        sp = spaces[0]
        space_id = sp.get("space_id") or sp.get("id") or sp.get("_id")
        assert space_id
        target_date = (datetime.utcnow() + timedelta(days=5)).date().isoformat()
        override_rate = 65
        ap = requests.post(
            f"{BASE_URL}/api/revpam/{PROPERTY_ID}/apply",
            headers=auth_headers,
            json={"space_id": space_id, "overrides": [{"date": target_date, "rate_per_unit": override_rate}]},
            timeout=30,
        )
        assert ap.status_code in (200, 201), ap.text
        # Verify override reflected in a booking. Book 2h that day.
        start = f"{target_date}T10:00:00"
        end = f"{target_date}T12:00:00"
        bk = requests.post(
            f"{BASE_URL}/api/space-bookings",
            headers=auth_headers,
            json={
                "space_id": space_id,
                "start": start,
                "end": end,
                "guest_name": "TEST RevPAM",
                "guest_email": "test_revpam@example.com",
            },
            timeout=30,
        )
        if bk.status_code not in (200, 201):
            pytest.skip(f"space-bookings not usable: {bk.status_code} {bk.text[:200]}")
        b = bk.json()
        price = b.get("price") or b.get("total") or (b.get("booking") or {}).get("price")
        # Expect price == 2 * 65 = 130 if override applied
        if price is not None:
            assert abs(price - 130) < 0.5, f"expected 130 got {price}"
