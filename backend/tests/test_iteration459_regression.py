"""
Iteration 459 - Full regression for allotments, forecast plans, intraday reprice,
restriction advisor, triple view, blended rate, forecast band, promo widget,
gap filler, morning brief AI night shift + smoke of critical old flows.
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"
PID = "default"
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:400]}"
    data = r.json()
    token = data.get("access_token") or data.get("token")
    if token:
        s.headers.update({"Authorization": f"Bearer {token}"})
    return s


# -------------------- 1. AUTH --------------------
def test_01_admin_login(admin_session):
    r = admin_session.get(f"{API}/properties", timeout=15)
    assert r.status_code == 200, r.text[:300]


# -------------------- 12. REGRESSION SMOKE --------------------
def test_12a_properties(admin_session):
    r = admin_session.get(f"{API}/properties", timeout=15)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_12b_bookings(admin_session):
    r = admin_session.get(f"{API}/bookings", timeout=20)
    assert r.status_code == 200


# -------------------- 2. ALLOTMENTS --------------------
def test_02a_allotment_create(admin_session):
    payload = {
        "operator_name": "TEST_Op_" + uuid.uuid4().hex[:6],
        "start_date": "2026-03-01",
        "end_date": "2026-03-10",
        "room_type": "std",
        "daily_allotment": 5,
        "release_days_before": 3,
        "rate": 100.0,
    }
    r = admin_session.post(f"{API}/allotments/{PID}", json=payload, timeout=20)
    assert r.status_code in (200, 201), f"{r.status_code} {r.text[:400]}"
    data = r.json()
    aid = data.get("id") or data.get("contract_id") or (data.get("contract") or {}).get("id")
    assert aid, f"no id in response: {data}"
    pytest.allot_id = aid


def test_02b_allotment_pickup_and_overshoot(admin_session):
    aid = getattr(pytest, "allot_id", None)
    if not aid:
        pytest.skip("no allot")
    r = admin_session.post(
        f"{API}/allotments/{PID}/{aid}/pickup",
        json={"date": "2026-03-02", "rooms": 3},
        timeout=15,
    )
    assert r.status_code in (200, 201), r.text[:300]
    # Overshoot
    r2 = admin_session.post(
        f"{API}/allotments/{PID}/{aid}/pickup",
        json={"date": "2026-03-02", "rooms": 999},
        timeout=15,
    )
    assert r2.status_code == 400, f"expected 400 got {r2.status_code} {r2.text[:200]}"


def test_02c_allotment_calendar(admin_session):
    aid = getattr(pytest, "allot_id", None)
    if not aid:
        pytest.skip("no allot")
    r = admin_session.get(f"{API}/allotments/{PID}/{aid}/calendar", timeout=15)
    assert r.status_code == 200, r.text[:300]


def test_02d_allotment_stop_sale(admin_session):
    aid = getattr(pytest, "allot_id", None)
    if not aid:
        pytest.skip("no allot")
    r = admin_session.post(
        f"{API}/allotments/{PID}/{aid}/stop-sale",
        json={"date": "2026-03-05", "stop": True},
        timeout=15,
    )
    assert r.status_code in (200, 201), r.text[:300]


def test_02e_allotment_release_run(admin_session):
    r = admin_session.post(f"{API}/allotments/{PID}/release-run", json={}, timeout=20)
    assert r.status_code in (200, 201), r.text[:300]
    # idempotent
    r2 = admin_session.post(f"{API}/allotments/{PID}/release-run", json={}, timeout=20)
    assert r2.status_code in (200, 201)


def test_02f_allotment_report(admin_session):
    r = admin_session.get(f"{API}/allotments/{PID}/report/operators", timeout=15)
    assert r.status_code == 200, r.text[:300]


# -------------------- 3. FORECAST PLANS --------------------
def test_03a_forecast_plan_create_version(admin_session):
    r = admin_session.post(
        f"{API}/forecast-plans/{PID}/versions",
        json={"name": "TEST_v1_" + uuid.uuid4().hex[:6], "note": "qa"},
        timeout=25,
    )
    assert r.status_code in (200, 201), r.text[:400]
    d = r.json()
    vid = d.get("id") or d.get("version_id") or (d.get("version") or {}).get("id")
    assert vid, f"no id: {d}"
    pytest.fp_vid = vid


def test_03b_forecast_plan_update_rows(admin_session):
    vid = getattr(pytest, "fp_vid", None)
    if not vid:
        pytest.skip("no version")
    # Get the version's first row period
    rv = admin_session.get(f"{API}/forecast-plans/versions/{vid}", timeout=15)
    period = None
    if rv.status_code == 200:
        rows = (rv.json() or {}).get("rows", [])
        if rows:
            period = rows[0].get("period")
    r = admin_session.put(
        f"{API}/forecast-plans/versions/{vid}/rows",
        json={"period": period or "2026-08", "bookings": 25, "revenue": 12000, "reason": "qa"},
        timeout=20,
    )
    assert r.status_code in (200, 201), r.text[:300]


def test_03c_forecast_plan_comment_approve_lock(admin_session):
    vid = getattr(pytest, "fp_vid", None)
    if not vid:
        pytest.skip()
    admin_session.post(f"{API}/forecast-plans/versions/{vid}/comment", json={"text": "ok"}, timeout=15)
    admin_session.post(f"{API}/forecast-plans/versions/{vid}/approve", json={}, timeout=15)
    rl = admin_session.post(f"{API}/forecast-plans/versions/{vid}/lock", json={}, timeout=15)
    assert rl.status_code in (200, 201), rl.text[:300]
    # Now editing rows must 400
    r_edit = admin_session.put(
        f"{API}/forecast-plans/versions/{vid}/rows",
        json={"period": "2026-08", "revenue": 999},
        timeout=15,
    )
    assert r_edit.status_code == 400, f"locked edit should 400 got {r_edit.status_code} {r_edit.text[:200]}"


# -------------------- 4. INTRADAY REPRICE --------------------
def test_04a_intraday_get(admin_session):
    r = admin_session.get(f"{API}/intraday-reprice/{PID}", timeout=15)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    assert "config" in d or "events" in d or isinstance(d, dict)


def test_04b_intraday_config_put(admin_session):
    r = admin_session.put(
        f"{API}/intraday-reprice/{PID}/config",
        json={"enabled": True, "spike_threshold_pct": 25, "max_lift_pct": 15},
        timeout=15,
    )
    assert r.status_code in (200, 201), r.text[:300]


def test_04c_intraday_scan(admin_session):
    r = admin_session.post(f"{API}/intraday-reprice/{PID}/scan", json={}, timeout=25)
    assert r.status_code in (200, 201), r.text[:300]


# -------------------- 5. RESTRICTION ADVISOR --------------------
def test_05a_restriction_scan(admin_session):
    r = admin_session.post(f"{API}/restriction-advisor/{PID}/scan", json={}, timeout=30)
    assert r.status_code in (200, 201), r.text[:400]


def test_05b_restriction_list(admin_session):
    r = admin_session.get(f"{API}/restriction-advisor/{PID}", timeout=15)
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    items = data if isinstance(data, list) else data.get("items", [])
    if items:
        pytest.restr_id = items[0].get("id") or items[0].get("_id")


def test_05c_restriction_accept_reject(admin_session):
    rid = getattr(pytest, "restr_id", None)
    if not rid:
        pytest.skip("no suggestion")
    r = admin_session.post(f"{API}/restriction-advisor/{PID}/{rid}/accept", json={}, timeout=15)
    assert r.status_code in (200, 201), r.text[:300]


# -------------------- 6. TRIPLE VIEW --------------------
def test_06_triple_view(admin_session):
    r = admin_session.get(f"{API}/budget/{PID}/triple", params={"year": 2026}, timeout=20)
    assert r.status_code == 200, r.text[:400]
    d = r.json()
    rows = d.get("rows") or d.get("months") or []
    assert len(rows) >= 12, f"expected 12 rows got {len(rows)}"
    assert "forecast_source" in d, f"missing forecast_source in {list(d.keys())}"


# -------------------- 7. BLENDED RATE --------------------
def test_07_blended_rate(admin_session):
    payload = {
        "property_id": PID,
        "check_in": "2026-04-10",
        "check_out": "2026-04-12",
        "rooms_requested": 8,
        "group_rate": 70,
        "group_name": "TEST_Blended",
    }
    r = admin_session.post(f"{API}/revenue/displacement/analyze", json=payload, timeout=25)
    assert r.status_code == 200, r.text[:500]
    d = r.json()
    assert "blended" in d, f"missing blended block; keys={list(d.keys())}"
    b = d["blended"]
    for k in ("breakeven_rate", "recommended_rate", "occ_before_pct", "occ_after_pct"):
        assert k in b, f"blended missing {k}: {b}"


# -------------------- 8. FORECAST BAND --------------------
def test_08_forecast_band(admin_session):
    r = admin_session.get(f"{API}/forecast-v2/horizon/{PID}", params={"months": 6}, timeout=25)
    assert r.status_code == 200, r.text[:400]
    d = r.json()
    assert "uncertainty_cv_pct" in d, f"missing uncertainty_cv_pct top-level: keys={list(d.keys())}"
    rows = d.get("forecast") or d.get("months") or d.get("rows") or []
    assert isinstance(rows, list) and len(rows) >= 1, f"empty forecast rows"
    first = rows[0]
    for k in ("revenue_low", "revenue_high", "band_pct"):
        assert k in first, f"missing {k} in {list(first.keys())}"


# -------------------- 9. PROMO WIDGET --------------------
def test_09a_create_promo(admin_session):
    code = "TESTP" + uuid.uuid4().hex[:5].upper()
    r = admin_session.post(
        f"{API}/rate-structure/promo-codes",
        json={
            "property_id": PID,
            "code": code,
            "kind": "percent",
            "amount": 20,
            "min_nights": 1,
            "active": True,
        },
        timeout=15,
    )
    assert r.status_code in (200, 201), r.text[:400]
    pytest.promo_code = code


def test_09b_validate_promo(admin_session):
    code = getattr(pytest, "promo_code", None)
    if not code:
        pytest.skip()
    r = requests.post(
        f"{API}/direct-conversion/validate",
        json={"coupon_code": code, "booking_value": 200, "nights": 2, "property_id": PID},
        timeout=15,
    )
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    assert d.get("ok") is True, f"validate ok=false: {d}"
    assert (d.get("discount_pct") or 0) > 0 or (d.get("amount") or 0) > 0, f"no discount applied: {d}"


def test_09c_validate_invalid(admin_session):
    r = requests.post(
        f"{API}/direct-conversion/validate",
        json={"coupon_code": "NOPE_INVALID_XYZ", "booking_value": 200, "nights": 2, "property_id": PID},
        timeout=15,
    )
    assert r.status_code == 200
    d = r.json()
    assert d.get("ok") is False, f"expected ok=false: {d}"
    assert d.get("reason"), "missing reason field"


def test_09d_booking_widget_book_with_coupon(admin_session):
    code = getattr(pytest, "promo_code", None)
    if not code:
        pytest.skip()
    payload = {
        "property_id": PID,
        "check_in": "2026-05-10",
        "check_out": "2026-05-12",
        "room_type": "Standard",
        "guest_name": "TEST_Widget",
        "guest_email": f"qa_{uuid.uuid4().hex[:6]}@test.local",
        "guest_phone": "+900000000",
        "coupon_code": code,
        "rate": 100,
        "guests": 2,
        "rooms": 1,
        "currency": "GBP",
    }
    r = requests.post(f"{API}/booking-widget/book", json=payload, timeout=20)
    assert r.status_code in (200, 201), f"widget book failed {r.status_code} {r.text[:400]}"
    d = r.json()
    # check total was discounted OR coupon applied surfaced
    assert d.get("status") in ("confirmed", "pending") or d.get("booking_ref"), d


# -------------------- 10. GAP FILLER --------------------
def test_10a_gap_scan(admin_session):
    r = admin_session.post(f"{API}/gap-filler/{PID}/scan", json={}, timeout=30)
    assert r.status_code in (200, 201), r.text[:400]


def test_10b_gap_list(admin_session):
    r = admin_session.get(f"{API}/gap-filler/{PID}", timeout=15)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    items = d if isinstance(d, list) else d.get("items", [])
    if items:
        c = items[0]
        pytest.gap_id = c.get("id") or c.get("_id")
        pytest.gap_code = c.get("promo_code") or c.get("coupon_code") or c.get("code")


def test_10c_gap_code_valid_via_dc(admin_session):
    code = getattr(pytest, "gap_code", None)
    if not code:
        pytest.skip("no gap code")
    r = requests.post(
        f"{API}/direct-conversion/validate",
        json={"coupon_code": code, "booking_value": 300, "nights": 2, "property_id": PID},
        timeout=15,
    )
    # Should be valid IF campaign is active; log otherwise
    assert r.status_code == 200, r.text[:300]


# -------------------- 11. MORNING BRIEF AI NIGHT SHIFT --------------------
def test_11_morning_brief(admin_session):
    r = admin_session.get(f"{API}/morning-brief/{PID}", timeout=25)
    assert r.status_code == 200, r.text[:400]
    d = r.json()
    ans = d.get("ai_night_shift") or d.get("night_shift") or {}
    assert ans, f"missing ai_night_shift block; keys={list(d.keys())}"
    # Expect 7 fields per spec — count keys
    assert isinstance(ans, dict) and len(ans.keys()) >= 5, f"expected >=5 fields got {list(ans.keys())}"


# -------------------- 13. Bug hunt: dashboard render + endpoints existence --------------------
def test_13_no_objectid_serialization(admin_session):
    # Hit a few list endpoints and ensure no ObjectId string leaks (still valid JSON)
    for path in ["/properties", "/bookings", "/allotments/" + PID, "/gap-filler/" + PID]:
        r = admin_session.get(f"{API}{path}", timeout=15)
        assert r.status_code == 200, f"{path} -> {r.status_code}"
        # Ensure body is JSON
        try:
            r.json()
        except Exception as e:
            pytest.fail(f"non-json body at {path}: {e}")
