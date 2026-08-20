"""
Regression suite iter 579 — Market Robot refactor, morning-brief KPIs,
demo-seeder scenarios, trial conversion, cloudbeds/pms/terminal, payments.
"""
import os
import pytest
import requests

def _read_env():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip()
    raise RuntimeError("REACT_APP_BACKEND_URL missing")


BASE_URL = _read_env().rstrip("/")
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PWD = "HotelAdmin2026!"
PID = "default"
CITY = "city-rooms"


@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PWD},
                      timeout=20)
    assert r.status_code == 200, r.text
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok
    return tok


@pytest.fixture(scope="session")
def h(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ---------- LOGIN ----------
def test_login_ok(admin_token):
    assert admin_token


# ---------- BOOKINGS ----------
def test_bookings_crud(h):
    payload = {
        "property_id": PID,
        "guest_name": "TEST_Regression",
        "guest_email": "test_reg@example.com",
        "check_in": "2026-06-01",
        "check_out": "2026-06-03",
        "room_type": "standard",
        "adults": 1,
        "channel": "direct",
        "total_amount": 200,
    }
    r = requests.post(f"{BASE_URL}/api/bookings", json=payload, headers=h, timeout=20)
    assert r.status_code in (200, 201), r.text
    bid = r.json().get("id") or r.json().get("_id") or r.json().get("booking_id")
    assert bid

    r = requests.get(f"{BASE_URL}/api/bookings?property_id={PID}", headers=h, timeout=20)
    assert r.status_code == 200

    # cleanup
    d = requests.delete(f"{BASE_URL}/api/bookings/{bid}", headers=h, timeout=20)
    assert d.status_code in (200, 204, 404)


# ---------- RMS (market robot refactor regression) ----------
@pytest.mark.parametrize("path", [
    f"/api/revenue/market-robot/{PID}/config",
    f"/api/revenue/market-robot/{PID}/supply?days=7",
    f"/api/revenue/market-robot/{PID}/competitors",
    f"/api/revenue/market-robot/{PID}/performance",
    f"/api/revenue/market-robot/{PID}/demand-dashboard?days=30",
    f"/api/revenue/market-robot/{PID}/market-pulse?days=30",
    f"/api/revenue/market-robot/{PID}/ranking?days=7",
    f"/api/revenue/market-robot/{PID}/weekly-summary",
])
def test_market_robot_endpoints(h, path):
    r = requests.get(f"{BASE_URL}{path}", headers=h, timeout=30)
    assert r.status_code == 200, f"{path} -> {r.status_code} {r.text[:200]}"


def test_close_gap_dry(h):
    r = requests.post(f"{BASE_URL}/api/revenue/market-robot/{PID}/close-gap",
                      json={"dry_run": True, "days": 7}, headers=h, timeout=30)
    assert r.status_code == 200, r.text


# ---------- CHANNELS ----------
def test_cloudbeds_status(h):
    r = requests.get(f"{BASE_URL}/api/cloudbeds/status/{PID}", headers=h, timeout=20)
    assert r.status_code == 200


def test_cloudbeds_certify_mock(h):
    r = requests.post(f"{BASE_URL}/api/cloudbeds/certify/{PID}", headers=h, timeout=30)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("passed") is True, j


def test_pms_providers(h):
    r = requests.get(f"{BASE_URL}/api/pms-connect/providers/{PID}", headers=h, timeout=20)
    assert r.status_code == 200


# ---------- PAYMENTS ----------
def test_stripe_checkout(h):
    r = requests.post(f"{BASE_URL}/api/payments/checkout",
                      json={"amount": 100, "origin_url": BASE_URL, "property_id": PID},
                      headers=h, timeout=30)
    assert r.status_code == 200, r.text
    j = r.json()
    assert "url" in j or "checkout_url" in j or "session_id" in j


def test_payments_txlog(h):
    r = requests.get(f"{BASE_URL}/api/payments/tx-log/{PID}", headers=h, timeout=20)
    assert r.status_code == 200


def test_terminal_readers(h):
    r = requests.get(f"{BASE_URL}/api/terminal/{PID}/readers", headers=h, timeout=20)
    assert r.status_code == 200


# ---------- TRIAL / EMAIL ----------
def test_trial_conversion_summary(h):
    r = requests.get(f"{BASE_URL}/api/trial-conversion/summary", headers=h, timeout=30)
    assert r.status_code == 200, r.text
    j = r.json()
    for k in ("metrics", "funnel", "weekly", "trials"):
        assert k in j, f"missing {k} in {list(j.keys())}"


def test_email_settings(h):
    r = requests.get(f"{BASE_URL}/api/email-settings", headers=h, timeout=20)
    assert r.status_code == 200
    j = r.json()
    assert j.get("live") is False


# ---------- DEMO SEEDER SCENARIOS ----------
def _clear_city(h):
    requests.post(f"{BASE_URL}/api/demo-seeder/clear/{CITY}", headers=h, timeout=30)


def test_scenario_high_season(h):
    _clear_city(h)
    r = requests.post(f"{BASE_URL}/api/demo-seeder/seed/{CITY}?scenario=high_season",
                      headers=h, timeout=60)
    assert r.status_code == 200, r.text
    assert r.json().get("created") == 45
    _clear_city(h)


def test_scenario_low_occupancy(h):
    _clear_city(h)
    r = requests.post(f"{BASE_URL}/api/demo-seeder/seed/{CITY}?scenario=low_occupancy",
                      headers=h, timeout=60)
    assert r.status_code == 200, r.text
    assert r.json().get("created") == 8
    _clear_city(h)


def test_scenario_group_heavy(h):
    _clear_city(h)
    r = requests.post(f"{BASE_URL}/api/demo-seeder/seed/{CITY}?scenario=group_heavy",
                      headers=h, timeout=60)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("created") == 30
    sample = j.get("sample") or j.get("bookings") or []
    grp = [b for b in sample if b.get("is_group") and b.get("channel") == "group"
           and 2 <= (b.get("rooms") or 1) <= 4]
    assert len(grp) > 0, f"no group bookings in sample: {sample[:2]}"
    _clear_city(h)


def test_scenario_invalid(h):
    r = requests.post(f"{BASE_URL}/api/demo-seeder/seed/{CITY}?scenario=xxx",
                      headers=h, timeout=20)
    assert r.status_code == 422, r.text


# ---------- MORNING BRIEF KPIs ----------
def test_morning_brief_kpis(h):
    r = requests.get(f"{BASE_URL}/api/morning-brief/{PID}", headers=h, timeout=30)
    assert r.status_code == 200, r.text
    j = r.json()
    today = j.get("today") or {}
    for k in ("occupancy_pct", "revenue", "adr", "revpar"):
        assert k in today, f"missing {k} in today={today}"
