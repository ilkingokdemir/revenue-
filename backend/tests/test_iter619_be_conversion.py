"""Iteration 619: Booking Engine Conversion Pack tests."""
import os
from datetime import datetime, timedelta, timezone

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://review-hub-108.preview.emergentagent.com").rstrip("/")
PID = "aldgate-flats"


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin_token(api):
    r = api.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"})
    assert r.status_code == 200, r.text
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok, r.text
    return tok


@pytest.fixture(scope="module")
def admin(api, admin_token):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json", "Authorization": f"Bearer {admin_token}"})
    return s


# ----------- price calendar -----------
def test_price_calendar():
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    r = requests.get(f"{BASE_URL}/api/booking/price-calendar/{PID}", params={"month": month, "adults": 2})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["month"] == month
    assert "days" in j and len(j["days"]) >= 28
    assert "currency" in j
    today = datetime.now(timezone.utc).date()
    for d in j["days"]:
        assert "date" in d and "min_price" in d and "available" in d
        assert "past" in d and "weekend" in d and "is_cheapest" in d and "sold_out" in d
        di = datetime.fromisoformat(d["date"]).date()
        if di < today:
            assert d["past"] is True
            assert d["min_price"] is None


# ----------- public rate plans -----------
def test_public_rate_plans_seeded():
    r = requests.get(f"{BASE_URL}/api/booking/rate-plans/{PID}")
    assert r.status_code == 200, r.text
    plans = r.json()
    codes = {p["code"]: p for p in plans}
    assert "flexible" in codes and "non_refundable" in codes and "breakfast" in codes
    assert codes["flexible"]["adjustment_value"] == 0
    assert codes["non_refundable"]["adjustment_value"] == -10
    assert codes["non_refundable"]["cancellation_type"] == "non_refundable"
    assert codes["non_refundable"]["deposit_pct"] == 100
    assert codes["breakfast"]["adjustment_type"] == "fixed_per_night"
    assert codes["breakfast"]["adjustment_value"] == 15
    assert "breakfast" in codes["breakfast"].get("includes", [])


# ----------- admin CRUD rate plans -----------
def test_admin_rate_plan_crud(admin):
    r = admin.get(f"{BASE_URL}/api/be-rate-plans/{PID}")
    assert r.status_code == 200, r.text
    initial = r.json()
    assert len(initial) >= 3

    # Create
    r = admin.post(f"{BASE_URL}/api/be-rate-plans/{PID}", json={
        "name": "TEST_QA_Plan",
        "adjustment_type": "pct",
        "adjustment_value": 5,
        "cancellation_type": "free",
        "free_cancel_hours": 24,
    })
    assert r.status_code == 200, r.text
    new_plan = r.json()
    pid_id = new_plan["id"]
    assert new_plan["name"] == "TEST_QA_Plan"

    # Update -> deactivate
    r = admin.put(f"{BASE_URL}/api/be-rate-plans/{PID}/{pid_id}", json={"is_active": False})
    assert r.status_code == 200, r.text
    assert r.json()["is_active"] is False

    # Public list must exclude inactive
    r = requests.get(f"{BASE_URL}/api/booking/rate-plans/{PID}")
    assert all(p["id"] != pid_id for p in r.json())

    # Delete
    r = admin.delete(f"{BASE_URL}/api/be-rate-plans/{PID}/{pid_id}")
    assert r.status_code == 200


# ----------- flex-dates -----------
def test_flex_dates():
    ci = (datetime.now(timezone.utc).date() + timedelta(days=10)).isoformat()
    co = (datetime.now(timezone.utc).date() + timedelta(days=12)).isoformat()
    r = requests.get(f"{BASE_URL}/api/booking/flex-dates/{PID}",
                     params={"check_in": ci, "check_out": co, "adults": 2})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["nights"] == 2
    assert "current" in j and "alternatives" in j and "best" in j
    today = datetime.now(timezone.utc).date()
    for a in j["alternatives"]:
        assert a["offset"] != 0
        assert datetime.fromisoformat(a["check_in"]).date() >= today
        assert "total" in a and "saving" in a and "saving_pct" in a


# ----------- reserve-multi -----------
def test_reserve_multi_and_get():
    # get non_refundable plan id
    plans = requests.get(f"{BASE_URL}/api/booking/rate-plans/{PID}").json()
    nr = next(p for p in plans if p["code"] == "non_refundable")

    ci = (datetime.now(timezone.utc).date() + timedelta(days=30)).isoformat()
    co = (datetime.now(timezone.utc).date() + timedelta(days=32)).isoformat()
    payload = {
        "property_id": PID,
        "guest_name": "TEST QA",
        "guest_email": "qa_test@example.com",
        "check_in": ci,
        "check_out": co,
        "adults": 2,
        "items": [
            {"room_type_id": "double-aldgate-flats", "rate_plan_id": "", "qty": 1},
            {"room_type_id": "double-aldgate-flats", "rate_plan_id": nr["id"], "qty": 2},
        ],
    }
    r = requests.post(f"{BASE_URL}/api/booking/reserve-multi", json=payload)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("booking_ref")
    assert j.get("cart_master") is True
    # expected: line1 = 89*2 = 178 (flexible), line2 = 89*0.9*2*2 = 320.4
    expected = 178 + 2 * 2 * 89 * 0.9
    assert abs(j["cart_total"] - expected) < 0.5, f"cart_total={j['cart_total']} expected~{expected}"
    assert j["total_price"] == j["cart_total"]
    assert len(j["cart_items"]) == 2
    refs = [it["booking_ref"] for it in j["cart_items"]]
    assert len(set(refs)) == 2  # distinct

    # get master
    r2 = requests.get(f"{BASE_URL}/api/booking/reservation/{j['booking_ref']}")
    assert r2.status_code == 200
    m = r2.json()
    assert m.get("cart_master") is True
    assert m.get("cart_total") == j["cart_total"]

    # get child (second)
    child_ref = refs[1]
    r3 = requests.get(f"{BASE_URL}/api/booking/reservation/{child_ref}")
    assert r3.status_code == 200
    c = r3.json()
    assert c["rate_plan_code"] == "non_refundable"
    assert c["rooms"] == 2

    # Empty items -> 422
    bad = dict(payload); bad["items"] = []
    r4 = requests.post(f"{BASE_URL}/api/booking/reserve-multi", json=bad)
    assert r4.status_code == 422

    # Unknown room -> 404
    bad2 = dict(payload); bad2["items"] = [{"room_type_id": "does-not-exist", "rate_plan_id": "", "qty": 1}]
    r5 = requests.post(f"{BASE_URL}/api/booking/reserve-multi", json=bad2)
    assert r5.status_code == 404


# ----------- regression: single-room widget endpoints -----------
def test_regression_property_and_rooms():
    r = requests.get(f"{BASE_URL}/api/booking/property/{PID}")
    assert r.status_code == 200

    ci = (datetime.now(timezone.utc).date() + timedelta(days=20)).isoformat()
    co = (datetime.now(timezone.utc).date() + timedelta(days=22)).isoformat()
    r = requests.get(f"{BASE_URL}/api/booking/rooms/{PID}", params={"check_in": ci, "check_out": co})
    assert r.status_code == 200
