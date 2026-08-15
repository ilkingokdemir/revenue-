"""Iteration 538 — quick re-verify of LOS/Wash/Metrics + Function Space endpoints."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://review-hub-108.preview.emergentagent.com").rstrip("/")
PID = "default"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"},
                      timeout=15)
    assert r.status_code == 200, r.text
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ---- LOS pricing / fences ----
def test_los_apply_default(auth):
    r = requests.post(f"{BASE_URL}/api/los-pricing/{PID}/apply", json={}, headers=auth, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "fences" in data or "applied" in data or "tiers" in data


def test_los_fences_active(auth):
    r = requests.get(f"{BASE_URL}/api/los-pricing/{PID}/fences?active=true", headers=auth, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    # should be list-like or dict with fences
    # Endpoint returns either list of fences or single config with active/tiers
    if isinstance(data, list):
        assert len(data) >= 1
    else:
        assert data.get("active") is True and data.get("tiers"), f"Not active: {data}"


# ---- Booking widget public ----
def test_booking_widget_los_discount():
    payload = {
        "property_id": PID,
        "check_in": "2026-03-01",
        "check_out": "2026-03-05",  # 4 nights → should trigger 3+ tier
        "guests": 2,
    }
    r = requests.post(f"{BASE_URL}/api/booking-widget/check-availability", json=payload, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    rooms = data.get("rooms", data.get("available_rooms", []))
    assert rooms, f"No rooms in response: {data}"
    # look for los_discount at any level
    joined = str(data)
    assert "los_discount" in joined or "los_discount_pct" in joined, f"No LOS discount fields: {joined[:400]}"


# ---- Modern metrics trend ----
def test_modern_metrics_trend(auth):
    r = requests.get(f"{BASE_URL}/api/modern-metrics/{PID}/trend?months=6", headers=auth, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    series = data.get("series") or data.get("months") or data.get("data") or data
    if isinstance(series, dict) and "series" in series:
        series = series["series"]
    # allow either list of 6 or dict with target keys
    assert "target_trevpor" in str(data) or "target_goppar" in str(data), f"No target keys in trend: {str(data)[:400]}"


# ---- Function space quote/proposal ----
def test_function_space_revpam(auth):
    r = requests.get(f"{BASE_URL}/api/function-space/{PID}/revpam", headers=auth, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    spaces = data.get("spaces") or data.get("data") or (data if isinstance(data, list) else [])
    assert spaces, f"No spaces in revpam: {data}"


def test_function_space_quote_and_proposal(auth):
    # First get a valid space id
    r = requests.get(f"{BASE_URL}/api/function-space/{PID}/revpam", headers=auth, timeout=15)
    data = r.json()
    spaces = data.get("spaces") or data.get("data") or (data if isinstance(data, list) else [])
    assert spaces
    space_id = spaces[0].get("space_id") or spaces[0].get("id") or spaces[0].get("code") or "MR-A"

    import uuid
    unique_date = "2026-05-" + str((int(uuid.uuid4().hex[:6], 16) % 27) + 1).zfill(2)
    quote_payload = {
        "space_id": space_id,
        "attendees": 6,
        "fnb": "coffee",
        "date": unique_date,
        "start_time": "09:00",
        "end_time": "17:00",
        "client_name": "TEST_Iter538",
    }
    r = requests.post(f"{BASE_URL}/api/function-space/{PID}/quote", json=quote_payload, headers=auth, timeout=15)
    assert r.status_code == 200, r.text
    quote = r.json()
    assert quote.get("total") or quote.get("total_price") or quote.get("quote_total"), f"No total in quote: {quote}"

    # Create proposal
    r2 = requests.post(f"{BASE_URL}/api/function-space/{PID}/proposals", json={**quote_payload, "quote": quote}, headers=auth, timeout=15)
    assert r2.status_code in (200, 201), r2.text
    prop = r2.json()
    proposal_obj = prop.get("proposal") if isinstance(prop.get("proposal"), dict) else prop
    pid_ = proposal_obj.get("id") or proposal_obj.get("proposal_id")
    assert pid_, f"No id in proposal: {prop}"

    # Accept
    r3 = requests.post(f"{BASE_URL}/api/function-space/{PID}/proposals/{pid_}/accept", json={}, headers=auth, timeout=15)
    assert r3.status_code == 200, r3.text
    acc = r3.json()
    assert acc.get("ok") and acc.get("booking", {}).get("status") == "confirmed", f"Accept response: {acc}"
