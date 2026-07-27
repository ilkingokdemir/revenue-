"""
Iteration 478 - Smart Rooms IoT + F&B Loyalty Bridge
Tests newly added endpoints:
  - Smart Rooms: list, control, scene, eco-sweep, energy summary, action log
  - F&B Tabs: loyalty-discount lookup + close with apply_loyalty=True

Requires admin login. Assumes property_id='aldgate-flats' has 22 rooms and
booking_id='48ae77e7-95fa-487f-8f01-1fbbbc4366fa' belongs to a Gold tier guest
in the 'default' loyalty config with 20% F&B discount.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or "http://localhost:8001"
PROPERTY = "aldgate-flats"
BOOKING_ID = "48ae77e7-95fa-487f-8f01-1fbbbc4366fa"

ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PWD = "HotelAdmin2026!"


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PWD})
    if r.status_code != 200:
        pytest.skip(f"Admin login failed: {r.status_code} {r.text[:200]}")
    data = r.json()
    token = data.get("access_token") or data.get("token")
    if token:
        s.headers.update({"Authorization": f"Bearer {token}"})
    return s


# ---------- Smart Rooms ----------
class TestSmartRooms:
    def test_list_rooms(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/smart-rooms/{PROPERTY}")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "rooms" in data and isinstance(data["rooms"], list)
        assert data["count"] >= 1
        first = data["rooms"][0]
        for k in ("room_id", "name", "devices"):
            assert k in first
        for dk in ("lights", "thermostat", "ac_mode", "curtains", "dnd", "tv"):
            assert dk in first["devices"]

    def test_control_lights_toggle(self, admin_session):
        rooms = admin_session.get(f"{BASE_URL}/api/smart-rooms/{PROPERTY}").json()["rooms"]
        rid = rooms[0]["room_id"]
        r = admin_session.post(
            f"{BASE_URL}/api/smart-rooms/{PROPERTY}/{rid}/control",
            json={"device": "lights", "value": True},
        )
        assert r.status_code == 200, r.text
        assert r.json()["devices"]["lights"] is True

    def test_thermostat_out_of_range(self, admin_session):
        rooms = admin_session.get(f"{BASE_URL}/api/smart-rooms/{PROPERTY}").json()["rooms"]
        rid = rooms[0]["room_id"]
        r = admin_session.post(
            f"{BASE_URL}/api/smart-rooms/{PROPERTY}/{rid}/control",
            json={"device": "thermostat", "value": 35},
        )
        assert r.status_code == 400

    def test_unknown_device(self, admin_session):
        rooms = admin_session.get(f"{BASE_URL}/api/smart-rooms/{PROPERTY}").json()["rooms"]
        rid = rooms[0]["room_id"]
        r = admin_session.post(
            f"{BASE_URL}/api/smart-rooms/{PROPERTY}/{rid}/control",
            json={"device": "toaster", "value": True},
        )
        assert r.status_code == 400

    def test_ac_mode_invalid(self, admin_session):
        rooms = admin_session.get(f"{BASE_URL}/api/smart-rooms/{PROPERTY}").json()["rooms"]
        rid = rooms[0]["room_id"]
        r = admin_session.post(
            f"{BASE_URL}/api/smart-rooms/{PROPERTY}/{rid}/control",
            json={"device": "ac_mode", "value": "turbo"},
        )
        assert r.status_code == 400

    def test_scene_welcome(self, admin_session):
        rooms = admin_session.get(f"{BASE_URL}/api/smart-rooms/{PROPERTY}").json()["rooms"]
        rid = rooms[0]["room_id"]
        r = admin_session.post(
            f"{BASE_URL}/api/smart-rooms/{PROPERTY}/{rid}/scene",
            json={"scene": "welcome"},
        )
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["scene"] == "welcome"
        assert j["devices"]["lights"] is True

    def test_scene_invalid(self, admin_session):
        rooms = admin_session.get(f"{BASE_URL}/api/smart-rooms/{PROPERTY}").json()["rooms"]
        rid = rooms[0]["room_id"]
        r = admin_session.post(
            f"{BASE_URL}/api/smart-rooms/{PROPERTY}/{rid}/scene",
            json={"scene": "party"},
        )
        assert r.status_code == 400

    def test_eco_sweep(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/smart-rooms/{PROPERTY}/eco-sweep")
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["ok"] is True
        assert "rooms_affected" in j and "kwh_saved" in j

    def test_energy_summary(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/smart-rooms/{PROPERTY}/energy/summary")
        assert r.status_code == 200, r.text
        j = r.json()
        for k in ("kwh_saved_30d", "cost_saved_30d", "eco_rooms", "actions_today"):
            assert k in j

    def test_actions_log(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/smart-rooms/{PROPERTY}/actions/log")
        assert r.status_code == 200, r.text
        j = r.json()
        assert "rows" in j and isinstance(j["rows"], list)


# ---------- F&B Loyalty Bridge ----------
class TestFnbLoyaltyBridge:
    def _create_tab(self, s, booking_id=BOOKING_ID):
        payload = {"property_id": PROPERTY, "outlet": "restaurant"}
        if booking_id:
            payload["booking_id"] = booking_id
        r = s.post(f"{BASE_URL}/api/fnb/tabs", json=payload)
        assert r.status_code in (200, 201), r.text
        return r.json()

    def _add_item(self, s, tab_id, name="Burger", qty=1, unit=50):
        r = s.post(f"{BASE_URL}/api/fnb/tabs/{tab_id}/items",
                   json={"name": name, "qty": qty, "unit_price": unit})
        assert r.status_code in (200, 201), r.text
        return r.json()

    def test_loyalty_discount_no_booking(self, admin_session):
        tab = self._create_tab(admin_session, booking_id=None)
        tid = tab.get("id") or tab.get("tab_id")
        r = admin_session.get(f"{BASE_URL}/api/fnb/tabs/{tid}/loyalty-discount")
        assert r.status_code == 200, r.text
        j = r.json()
        assert j.get("eligible") is False
        assert j.get("reason") == "no_booking"

    def test_loyalty_discount_gold_eligible(self, admin_session):
        tab = self._create_tab(admin_session)
        tid = tab.get("id") or tab.get("tab_id")
        r = admin_session.get(f"{BASE_URL}/api/fnb/tabs/{tid}/loyalty-discount")
        assert r.status_code == 200, r.text
        j = r.json()
        assert j.get("eligible") is True, j
        assert j.get("tier_key") == "gold"
        assert j.get("discount_pct") == 20

    def test_close_with_apply_loyalty(self, admin_session):
        tab = self._create_tab(admin_session)
        tid = tab.get("id") or tab.get("tab_id")
        self._add_item(admin_session, tid, name="Pasta", qty=1, unit=50)
        r = admin_session.post(
            f"{BASE_URL}/api/fnb/tabs/{tid}/close",
            json={"payment_method": "room_folio", "apply_loyalty": True},
        )
        assert r.status_code == 200, r.text
        j = r.json()
        assert j.get("loyalty_applied") is True, j
        assert j.get("effective_discount_pct") == 20
        assert j.get("charged_to_folio") is True
        # total should be 50 * 0.8 = 40 (allowing for tax variations, but likely exact)
        total = j.get("total") or j.get("grand_total") or j.get("amount")
        assert total is not None
        assert abs(float(total) - 40.0) < 0.01, f"Expected ~40.0 got {total}"


# ---------- Regression ----------
class TestRegression:
    def test_demo_requests(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/demo-requests")
        assert r.status_code == 200

    def test_close_tab_no_loyalty_cash(self, admin_session):
        payload = {"property_id": PROPERTY, "outlet": "restaurant"}
        tab = admin_session.post(f"{BASE_URL}/api/fnb/tabs", json=payload).json()
        tid = tab.get("id") or tab.get("tab_id")
        admin_session.post(f"{BASE_URL}/api/fnb/tabs/{tid}/items",
                           json={"name": "Coffee", "qty": 2, "unit_price": 5})
        r = admin_session.post(f"{BASE_URL}/api/fnb/tabs/{tid}/close",
                               json={"payment_method": "cash"})
        assert r.status_code == 200, r.text
        j = r.json()
        assert j.get("loyalty_applied") in (False, None)
