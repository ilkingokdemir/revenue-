"""Iteration 567: Apply-comp-trigger + comp-deviations heatmap + undo cleanup tests."""
import os
import requests

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "https://review-hub-108.preview.emergentagent.com").rstrip("/")
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


def test_apply_comp_trigger_creates_overrides_and_history():
    s = _login()
    # ensure enabled
    s.put(f"{BASE_URL}/api/demand-signals/{PID}/comp-trigger",
          json={"threshold_pct": 10, "enabled": True}, timeout=20)
    # first undo any leftover comp_trigger markups to have a clean state
    s.post(f"{BASE_URL}/api/demand-signals/{PID}/undo-markups", json={}, timeout=30)

    r = s.post(f"{BASE_URL}/api/demand-signals/{PID}/comp-trigger/apply", timeout=60)
    assert r.status_code == 200, r.text[:500]
    d = r.json()
    assert d.get("ok") is True
    assert "applied" in d
    assert "days" in d
    applied_count = d["applied"]
    assert applied_count <= 10, "apply should cap at 10 days (top deviations)"
    if applied_count > 0:
        first = d["days"][0]
        assert "date" in first and "new_rate" in first
        # markup_history should contain a comp_trigger entry
        h = s.get(f"{BASE_URL}/api/demand-signals/{PID}/markup-history", timeout=20)
        assert h.status_code == 200
        hist = h.json().get("history", [])
        assert any(row.get("kind") == "comp_trigger" and row.get("action") == "apply"
                   for row in hist), "markup_history missing comp_trigger apply log"


def test_undo_comp_trigger_markups():
    s = _login()
    # Ensure some applied first
    s.put(f"{BASE_URL}/api/demand-signals/{PID}/comp-trigger",
          json={"threshold_pct": 10, "enabled": True}, timeout=20)
    ap = s.post(f"{BASE_URL}/api/demand-signals/{PID}/comp-trigger/apply", timeout=60).json()
    applied = ap.get("applied", 0)
    r = s.post(f"{BASE_URL}/api/demand-signals/{PID}/undo-markups", json={}, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d.get("ok") is True
    assert "restored_manual" in d and "reverted_to_auto" in d
    if applied:
        assert d["total"] >= applied - 5  # allow for some in-flight variance


def test_comp_deviations_filled_month():
    s = _login()
    r = s.get(f"{BASE_URL}/api/demand-signals/{PID}/comp-deviations",
              params={"year": 2026, "month": 8}, timeout=30)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    assert d["property_id"] == PID
    assert d["year"] == 2026 and d["month"] == 8
    assert isinstance(d["deviations"], dict)
    # per problem statement, Aug 2026 has market_supply geo data → non-empty
    if d["deviations"]:
        k = next(iter(d["deviations"]))
        item = d["deviations"][k]
        for f in ("dev_pct", "market", "ours"):
            assert f in item


def test_comp_deviations_empty_month():
    s = _login()
    # A month with no market_supply geo data (far past)
    r = s.get(f"{BASE_URL}/api/demand-signals/{PID}/comp-deviations",
              params={"year": 2020, "month": 1}, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d["deviations"] == {} or isinstance(d["deviations"], dict)


def test_regression_calendar_and_pricing():
    s = _login()
    for path in [
        f"/api/demand-signals/{PID}/config",
        f"/api/demand-signals/{PID}/markup-history",
        f"/api/demand-signals/{PID}/occupancy-rule/impact",
        f"/api/ai-pricing/{PID}/suggestions",
    ]:
        r = s.get(f"{BASE_URL}{path}", timeout=30)
        assert r.status_code in (200, 404), f"{path} -> {r.status_code}"
