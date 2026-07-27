"""Owner Pulse backend regression — iteration 466."""
import os
import pytest
import requests

def _load_env():
    p = "/app/frontend/.env"
    if os.path.exists(p):
        for line in open(p):
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.strip().split("=", 1)
                os.environ.setdefault(k, v)
_load_env()
BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE}/api"
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PWD = "HotelAdmin2026!"
OWNER_EMAIL = "pulse_owner@test.com"
OWNER_PIN = "862347"
PID = "default"
MODULE_KEYS = ["dashboard", "demand_radar", "compset", "reports", "rates", "portfolio"]


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PWD}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def owner_token():
    r = requests.post(f"{API}/owner-auth/login", json={"email": OWNER_EMAIL, "pin": OWNER_PIN}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _oh(t): return {"Authorization": f"Bearer {t}"}


@pytest.fixture(scope="module", autouse=True)
def restore_modules_at_end(admin_token):
    yield
    # Guarantee all modules enabled at end
    all_on = {k: True for k in MODULE_KEYS}
    requests.put(f"{API}/owner-pulse/{PID}/config", json={"modules": all_on},
                 headers=_oh(admin_token), timeout=15)


class TestOwnerPortal:
    def test_dashboard_shape(self, owner_token):
        r = requests.get(f"{API}/owner-pulse/portal/dashboard", headers=_oh(owner_token), timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert len(d["month_cards"]) == 3
        assert len(d["occ_series"]) == 90
        assert len(d["annual"]["rows"]) == 12
        for c in d["month_cards"]:
            for k in ("revenue", "occ", "adr", "label", "tag", "month"):
                assert k in c

    def test_demand_radar(self, owner_token):
        r = requests.get(f"{API}/owner-pulse/portal/demand-radar", headers=_oh(owner_token), timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "daily" in d and len(d["daily"]) == 90

    def test_booking_behavior(self, owner_token):
        r = requests.get(f"{API}/owner-pulse/portal/booking-behavior", headers=_oh(owner_token), timeout=30)
        assert r.status_code == 200, r.text

    def test_compset(self, owner_token):
        r = requests.get(f"{API}/owner-pulse/portal/compset", headers=_oh(owner_token), timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "daily" in d and len(d["daily"]) == 30

    @pytest.mark.parametrize("key", ["performance", "yoy", "bookings", "source"])
    def test_reports(self, owner_token, key):
        r = requests.get(f"{API}/owner-pulse/portal/reports/{key}", headers=_oh(owner_token), timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "columns" in d and "rows" in d and "title" in d
        assert isinstance(d["rows"], list)

    def test_config(self, owner_token):
        r = requests.get(f"{API}/owner-pulse/portal/config", headers=_oh(owner_token), timeout=15)
        assert r.status_code == 200
        assert set(r.json()["modules"].keys()) == set(MODULE_KEYS)


class TestAdmin:
    def test_admin_get_config(self, admin_token):
        r = requests.get(f"{API}/owner-pulse/{PID}/config", headers=_oh(admin_token), timeout=15)
        assert r.status_code == 200
        assert set(r.json()["modules"].keys()) == set(MODULE_KEYS)

    def test_admin_preview_dashboard(self, admin_token):
        r = requests.get(f"{API}/owner-pulse/{PID}/dashboard", headers=_oh(admin_token), timeout=30)
        assert r.status_code == 200
        assert len(r.json()["month_cards"]) == 3


class TestModuleGating:
    def test_disable_compset_returns_403(self, admin_token, owner_token):
        mods = {k: True for k in MODULE_KEYS}
        mods["compset"] = False
        r = requests.put(f"{API}/owner-pulse/{PID}/config", json={"modules": mods},
                         headers=_oh(admin_token), timeout=15)
        assert r.status_code == 200
        r2 = requests.get(f"{API}/owner-pulse/portal/compset", headers=_oh(owner_token), timeout=15)
        assert r2.status_code == 403
        # Re-enable
        mods["compset"] = True
        r3 = requests.put(f"{API}/owner-pulse/{PID}/config", json={"modules": mods},
                          headers=_oh(admin_token), timeout=15)
        assert r3.status_code == 200
        r4 = requests.get(f"{API}/owner-pulse/portal/compset", headers=_oh(owner_token), timeout=30)
        assert r4.status_code == 200


class TestAuthGating:
    def test_admin_token_rejected_on_owner_endpoint(self, admin_token):
        r = requests.get(f"{API}/owner-pulse/portal/dashboard", headers=_oh(admin_token), timeout=15)
        assert r.status_code == 401

    def test_missing_token(self):
        r = requests.get(f"{API}/owner-pulse/portal/dashboard", timeout=15)
        assert r.status_code in (401, 403)

    def test_owner_cannot_call_admin_config(self, owner_token):
        r = requests.get(f"{API}/owner-pulse/{PID}/config", headers=_oh(owner_token), timeout=15)
        assert r.status_code in (401, 403)
