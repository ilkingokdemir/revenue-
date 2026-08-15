"""Iteration 550 — Push Drift Verification, Reservation Import to OTB,
Weekly Partner Report, Night-Push verify integration, regressions.
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
PID = "default"
ADMIN = {"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"}


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json=ADMIN)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:200]}"
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok
    s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


# --- 1) Mews verify-push: LIVE read-back ---
def test_mews_verify_push_live(client):
    # Ensure there is a fresh push to verify against
    r = client.post(f"{BASE_URL}/api/pms-connect/mews/push-from-rms/{PID}", json={"days": 2}, timeout=90)
    assert r.status_code == 200, r.text
    assert r.json().get("mocked") is False

    r = client.post(f"{BASE_URL}/api/pms-connect/mews/verify-push/{PID}", json={}, timeout=120)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("ok") is True, f"verify not ok: {d}"
    assert d.get("mocked") is False, f"expected live read-back, got {d}"
    assert "rows" in d and isinstance(d["rows"], list) and len(d["rows"]) >= 1
    for row in d["rows"]:
        # pushed & channel prices should be present
        assert "pushed" in row or "pushed_price" in row
        assert "channel" in row or "channel_price" in row
        assert "drift_pct" in row
    assert "max_drift_pct" in d
    # Live Mews expected 0.0 drift
    assert d["max_drift_pct"] <= 0.5, f"drift too high: {d['max_drift_pct']}"


# --- 2) Siteminder verify-push mocked ---
def test_siteminder_verify_push_mocked(client):
    # Push first (mock)
    client.post(f"{BASE_URL}/api/pms-connect/siteminder/push-from-rms/{PID}", json={"days": 2})
    r = client.post(f"{BASE_URL}/api/pms-connect/siteminder/verify-push/{PID}", json={})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("mocked") is True
    assert "rows" in d
    if d["rows"]:
        assert all("drift_pct" in row for row in d["rows"])


# --- 3) Unknown provider -> 404 ---
def test_verify_push_unknown_provider(client):
    r = client.post(f"{BASE_URL}/api/pms-connect/unknown/verify-push/{PID}", json={})
    assert r.status_code == 404


# --- 4) Import to OTB (Mews) — 200 imported, idempotent ---
def test_import_to_otb_mews_and_idempotent(client):
    r = client.post(f"{BASE_URL}/api/pms-connect/mews/import-to-otb/{PID}", json={}, timeout=180)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("ok") is True, f"import not ok: {d}"
    imported_1 = d.get("imported", 0)
    assert imported_1 >= 1, f"expected >=1 imported, got {imported_1}"
    otb14 = d.get("otb_contribution_next14")
    # non-fatal but expected per problem statement
    assert otb14 is None or isinstance(otb14, (int, float))

    # Re-run should be idempotent
    r2 = client.post(f"{BASE_URL}/api/pms-connect/mews/import-to-otb/{PID}", json={}, timeout=180)
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2.get("ok") is True
    # imported might be 0 (nothing new) or same set; totals in db should not double
    total_1 = d.get("total_in_db") or d.get("total") or imported_1
    total_2 = d2.get("total_in_db") or d2.get("total") or d2.get("imported", 0)
    # allow small diff (new reservations may have appeared)
    if isinstance(total_1, int) and isinstance(total_2, int):
        assert abs(total_2 - total_1) <= max(50, int(0.25 * total_1)), \
            f"idempotency broken: {total_1} -> {total_2}"


# --- 5) Weekly report Turkish ---
def test_weekly_report_turkish(client):
    r = client.get(f"{BASE_URL}/api/pms-connect/weekly-report/{PID}", timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "email_subject" in d and len(d["email_subject"]) > 0
    body = d.get("email_body", "")
    assert "PMS BAĞLANTI MERKEZİ" in body, f"missing header in body: {body[:300]}"
    assert "channels" in d and isinstance(d["channels"], list)
    for ch in d["channels"]:
        assert "pushes_7d" in ch
    # drift_alerts_7d is a top-level counter
    assert "drift_alerts_7d" in d
    assert isinstance(d["drift_alerts_7d"], int)


# --- 6) Night push includes verify_ok + max_drift_pct ---
def test_night_push_includes_verify_fields(client):
    client.post(f"{BASE_URL}/api/pms-connect/night-push/{PID}", json={"enabled": True})
    r = client.post(f"{BASE_URL}/api/pms-connect/night-push/{PID}/run", json={}, timeout=180)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "results" in d and isinstance(d["results"], list) and len(d["results"]) >= 1
    # At least one result (mews) should include verify_ok
    mews_results = [r for r in d["results"] if r.get("provider") == "mews" or r.get("id") == "mews"]
    assert mews_results, f"no mews in results: {d['results']}"
    mr = mews_results[0]
    assert "verify_ok" in mr, f"verify_ok missing in mews result: {mr}"
    assert "max_drift_pct" in mr, f"max_drift_pct missing in mews result: {mr}"
    client.post(f"{BASE_URL}/api/pms-connect/night-push/{PID}", json={"enabled": False})


# --- 7) Regressions ---
@pytest.mark.parametrize("path", [
    "/api/revenue/ai-pricing/default/suggestions?days=3&use_llm=false",
    "/api/net-otb/default?days=7",
    "/api/pms-connect/health/default",
])
def test_regression_endpoints(client, path):
    r = client.get(f"{BASE_URL}{path}", timeout=60)
    assert r.status_code == 200, f"{path} -> {r.status_code} {r.text[:200]}"


def test_pms_connect_health_has_7_channels(client):
    r = client.get(f"{BASE_URL}/api/pms-connect/health/{PID}")
    assert r.status_code == 200
    ids = [c["id"] for c in r.json()["channels"]]
    expected = {"mews", "apaleo", "siteminder", "eviivo", "elektraweb", "cloudbeds", "hotelrunner"}
    assert expected.issubset(set(ids)), f"Missing: {expected - set(ids)}"


def test_mews_push_still_live(client):
    r = client.post(f"{BASE_URL}/api/pms-connect/mews/push-from-rms/{PID}", json={"days": 2}, timeout=90)
    assert r.status_code == 200
    assert r.json().get("mocked") is False
