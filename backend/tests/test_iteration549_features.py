"""Iteration 549 — Partner Kit, Mews live regression, Health Board, Night-Push,
Elasticity history, Public Events distance, Pitch archive."""
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


# --- 1) Health Board 7 channels ---
def test_health_board_7_channels(client):
    r = client.get(f"{BASE_URL}/api/pms-connect/health/{PID}")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "channels" in data
    ids = [c["id"] for c in data["channels"]]
    expected = {"mews", "apaleo", "siteminder", "eviivo", "elektraweb", "cloudbeds", "hotelrunner"}
    assert expected.issubset(set(ids)), f"Missing channels: {expected - set(ids)}"
    assert isinstance(data.get("auto_night_push"), bool)
    for ch in data["channels"]:
        for k in ("mode", "certified", "last_push_at", "total_pushes", "error_rate_pct"):
            assert k in ch, f"Missing key {k} in channel {ch.get('id')}"


# --- 2) Night push toggle + run ---
def test_night_push_toggle_and_run(client):
    r = client.post(f"{BASE_URL}/api/pms-connect/night-push/{PID}", json={"enabled": True})
    assert r.status_code == 200, r.text
    assert r.json().get("ok") is True

    r = client.post(f"{BASE_URL}/api/pms-connect/night-push/{PID}/run", json={})
    assert r.status_code == 200, r.text
    d = r.json()
    assert "results" in d and isinstance(d["results"], list)

    r = client.get(f"{BASE_URL}/api/pms-connect/health/{PID}")
    assert r.status_code == 200
    assert "last_night_push" in r.json() or any(
        c.get("last_push_at") for c in r.json().get("channels", [])
    )

    # reset
    r = client.post(f"{BASE_URL}/api/pms-connect/night-push/{PID}", json={"enabled": False})
    assert r.status_code == 200


# --- 3) Morning report includes night_push when enabled ---
def test_morning_report_with_night_push(client):
    client.post(f"{BASE_URL}/api/pms-connect/night-push/{PID}", json={"enabled": True})
    r = client.post(f"{BASE_URL}/api/morning-report/{PID}/run", json={})
    assert r.status_code == 200, r.text
    d = r.json()
    # audit should be present; night_push key expected
    body = d.get("audit", d)
    assert "night_push" in body or "night_push" in d, f"night_push not in response: {list(d.keys())}"
    client.post(f"{BASE_URL}/api/pms-connect/night-push/{PID}", json={"enabled": False})


# --- 4) Partner kits ---
@pytest.mark.parametrize("provider,fmt_hint", [
    ("siteminder", "OTA"),
    ("eviivo", ""),
])
def test_partner_kit(client, provider, fmt_hint):
    r = client.get(f"{BASE_URL}/api/pms-connect/{provider}/partner-kit/{PID}")
    assert r.status_code == 200, r.text
    d = r.json()
    assert "email_subject" in d
    assert "email_body" in d
    assert len(d["email_body"]) > 500, f"body only {len(d['email_body'])} chars"
    assert "tech_summary" in d and "format" in d["tech_summary"]
    if provider == "siteminder":
        assert "OTA" in d["tech_summary"]["format"]
        assert "2-Way ARI" in d["email_body"] or "ARI" in d["email_body"]


# --- 5) Elasticity history ---
def test_elasticity_history(client):
    r = client.get(f"{BASE_URL}/api/elasticity/{PID}")
    assert r.status_code == 200, r.text
    r = client.get(f"{BASE_URL}/api/elasticity/{PID}/history")
    assert r.status_code == 200, r.text
    d = r.json()
    assert "history" in d and isinstance(d["history"], list)
    assert len(d["history"]) >= 1
    entry = d["history"][-1]
    assert "month" in entry
    assert "elasticity" in entry
    assert "aggressiveness" in entry


# --- 6) Public events distance estimate ---
def test_distance_estimate(client):
    try:
        r = client.post(
            f"{BASE_URL}/api/public-events/estimate-distance",
            json={"venue_name": "Hallenstadion", "property_id": PID},
            timeout=30,
        )
    except requests.exceptions.RequestException as e:
        pytest.skip(f"Nominatim external transient: {e}")
    if r.status_code == 502:
        pytest.skip("Nominatim upstream 502 — external service transient")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("ok") is True
    assert "distance_km" in d
    assert isinstance(d["distance_km"], (int, float))


def test_distance_estimate_missing_venue(client):
    r = client.post(
        f"{BASE_URL}/api/public-events/estimate-distance",
        json={"property_id": PID},
    )
    assert r.status_code == 400, r.text


# --- 7) Pitch archive ---
def test_pitch_archive_flow(client):
    r = client.get(f"{BASE_URL}/api/simulator/{PID}/pitch-pdf?days=7&base_rate=100")
    assert r.status_code == 200, r.text
    assert "pdf" in r.headers.get("content-type", "").lower()
    time.sleep(1)
    r = client.get(f"{BASE_URL}/api/simulator/{PID}/pitch-archive")
    assert r.status_code == 200, r.text
    d = r.json()
    assert "archive" in d and isinstance(d["archive"], list) and len(d["archive"]) >= 1
    item = d["archive"][0]
    for k in ("id", "days", "base_rate", "size_kb"):
        assert k in item, f"missing {k}"
    r = client.get(f"{BASE_URL}/api/simulator/pitch-archive/{item['id']}/download")
    assert r.status_code == 200, r.text
    assert "pdf" in r.headers.get("content-type", "").lower()


# --- 8) Mews LIVE regression ---
def test_mews_live_regression(client):
    r = client.get(f"{BASE_URL}/api/pms-connect/providers/{PID}")
    assert r.status_code == 200
    mews = next(p for p in r.json()["providers"] if p["id"] == "mews")
    assert mews.get("mode") == "live", f"mews mode: {mews.get('mode')}"
    cert = mews.get("certification") or {}
    assert cert.get("passed") is True or cert.get("mode") == "live", f"cert: {cert}"

    r = client.post(f"{BASE_URL}/api/pms-connect/mews/push-from-rms/{PID}", json={"days": 2})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("mocked") is False, f"expected mocked=false, got {d}"
    assert d.get("pushed_days") == 2 or d.get("days") == 2


# --- 9) Regression endpoints ---
@pytest.mark.parametrize("path", [
    "/api/pms-connect/mews/log/default",
    "/api/cloudbeds/status/default",
    "/api/hotelrunner/status/default",
    "/api/revenue/ai-pricing/default/suggestions?days=3&use_llm=false",
])
def test_regression_endpoints(client, path):
    r = client.get(f"{BASE_URL}{path}")
    assert r.status_code == 200, f"{path} -> {r.status_code} {r.text[:200]}"
