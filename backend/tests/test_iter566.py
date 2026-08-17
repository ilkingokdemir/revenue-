"""Iteration 566: Occupancy Rule Impact + Competitor Price Trigger tests."""
import os
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://review-hub-108.preview.emergentagent.com").rstrip("/")
PID = "default"
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASS = "HotelAdmin2026!"


def _login():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    tok = r.json().get("access_token") or r.json().get("token")
    if tok:
        s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


def test_occupancy_rule_impact():
    s = _login()
    r = s.get(f"{BASE_URL}/api/demand-signals/{PID}/occupancy-rule/impact", timeout=20)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    assert d["property_id"] == PID
    assert isinstance(d.get("months"), list)
    assert "note" in d


def test_occupancy_rule_run_then_impact():
    s = _login()
    r = s.post(f"{BASE_URL}/api/demand-signals/{PID}/occupancy-rule/run", timeout=60)
    assert r.status_code == 200, r.text[:300]
    r2 = s.get(f"{BASE_URL}/api/demand-signals/{PID}/occupancy-rule/impact", timeout=20)
    assert r2.status_code == 200
    assert isinstance(r2.json().get("months"), list)


def test_comp_trigger_get():
    s = _login()
    r = s.get(f"{BASE_URL}/api/demand-signals/{PID}/comp-trigger", timeout=20)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    assert "threshold_pct" in d
    assert "enabled" in d
    assert isinstance(d["threshold_pct"], (int, float))
    assert isinstance(d["enabled"], bool)


def test_comp_trigger_put_clamp():
    s = _login()
    # clamp low
    r = s.put(f"{BASE_URL}/api/demand-signals/{PID}/comp-trigger",
              json={"threshold_pct": 1, "enabled": True}, timeout=20)
    assert r.status_code == 200
    assert r.json()["threshold_pct"] >= 3.0
    # clamp high
    r = s.put(f"{BASE_URL}/api/demand-signals/{PID}/comp-trigger",
              json={"threshold_pct": 999}, timeout=20)
    assert r.status_code == 200
    assert r.json()["threshold_pct"] <= 50.0
    # normal
    r = s.put(f"{BASE_URL}/api/demand-signals/{PID}/comp-trigger",
              json={"threshold_pct": 10, "enabled": True}, timeout=20)
    assert r.status_code == 200
    assert abs(r.json()["threshold_pct"] - 10.0) < 0.01
    assert r.json()["enabled"] is True


def test_comp_trigger_run_and_notification():
    s = _login()
    # ensure enabled with reasonable threshold
    s.put(f"{BASE_URL}/api/demand-signals/{PID}/comp-trigger",
          json={"threshold_pct": 10, "enabled": True}, timeout=20)
    r = s.post(f"{BASE_URL}/api/demand-signals/{PID}/comp-trigger/run", timeout=60)
    assert r.status_code == 200, r.text[:500]
    d = r.json()
    assert d.get("ran") is True
    assert "deviations" in d
    assert "deviation_days" in d
    # notifications endpoint check
    r2 = s.get(f"{BASE_URL}/api/notifications", timeout=20)
    if r2.status_code == 200:
        items = r2.json() if isinstance(r2.json(), list) else r2.json().get("items", [])
        # not strictly asserting existence in case none deviated, just structure check
        assert isinstance(items, list)


def test_regression_ai_pricing_and_signals():
    s = _login()
    for path in [
        f"/api/demand-signals/{PID}/config",
        f"/api/ai-pricing/{PID}/suggestions",
    ]:
        r = s.get(f"{BASE_URL}{path}", timeout=30)
        assert r.status_code in (200, 404), f"{path} -> {r.status_code}"
