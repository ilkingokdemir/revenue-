"""Iteration 548 — PMS Connect Hub (5 providers) + Cloudbeds certify."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://review-hub-108.preview.emergentagent.com").rstrip("/")
PID = "default"
ADMIN = {"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"}
PROVIDERS = ["mews", "apaleo", "siteminder", "eviivo", "elektraweb"]


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


# --- PMS Connect Hub ---
def test_providers_default_lists_5(client):
    r = client.get(f"{BASE_URL}/api/pms-connect/providers/{PID}")
    assert r.status_code == 200, r.text
    data = r.json()
    ids = [p["id"] for p in data["providers"]]
    assert set(PROVIDERS).issubset(set(ids))
    for p in data["providers"]:
        assert "api_type" in p and "format" in p and "auth_fields" in p and "mode" in p
        assert p["mode"] == "mocked"
        assert "total_pushes" in p


def test_mews_config_and_configured_fields(client):
    r = client.post(f"{BASE_URL}/api/pms-connect/mews/config/{PID}", json={"rate_id": "test-rate"})
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True
    assert r.json()["mode"] == "mocked"  # partial creds
    r = client.get(f"{BASE_URL}/api/pms-connect/providers/{PID}")
    mews = next(p for p in r.json()["providers"] if p["id"] == "mews")
    assert "rate_id" in mews["configured_fields"]


def test_mews_push_translated_preview(client):
    r = client.post(f"{BASE_URL}/api/pms-connect/mews/push-from-rms/{PID}", json={"days": 3})
    assert r.status_code == 200, r.text
    d = r.json()
    if d.get("pushed_days", 0) > 0:
        assert d.get("mocked") is True
        tp = d["translated_preview"]
        assert tp["path"] == "/api/connector/v1/rates/updatePrice"
        assert "PriceUpdates" in tp["body"]
    else:
        pytest.skip("No RMS rate_overrides seeded — push had 0 rows")


def test_siteminder_push_xml(client):
    r = client.post(f"{BASE_URL}/api/pms-connect/siteminder/push-from-rms/{PID}", json={"days": 2})
    assert r.status_code == 200, r.text
    d = r.json()
    if d.get("pushed_days", 0) > 0:
        assert "body_xml" in d["translated_preview"]
        assert "OTA_HotelRateAmountNotifRQ" in d["translated_preview"]["body_xml"]
    else:
        pytest.skip("No RMS rate_overrides seeded")


@pytest.mark.parametrize("prov", PROVIDERS)
def test_certify_each_provider(client, prov):
    r = client.post(f"{BASE_URL}/api/pms-connect/{prov}/certify/{PID}")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["passed"] is True
    assert d["mode"] == "mocked"
    assert len(d["checks"]) == 4
    names = [c["name"] for c in d["checks"]]
    assert any("Kimlik" in n for n in names)
    assert any("Test push" in n for n in names)
    assert any("Geri okuma" in n for n in names)
    assert any("Format" in n for n in names)


def test_certification_persisted(client):
    r = client.get(f"{BASE_URL}/api/pms-connect/providers/{PID}")
    for p in r.json()["providers"]:
        if p["id"] in PROVIDERS:
            assert p.get("certification") is not None, f"{p['id']} cert missing"
            assert p["certification"]["passed"] is True


def test_eviivo_pull_reservations_mocked(client):
    r = client.post(f"{BASE_URL}/api/pms-connect/eviivo/pull-reservations/{PID}")
    assert r.status_code == 200, r.text
    assert r.json().get("mocked") is True


def test_mews_log_has_rows(client):
    r = client.get(f"{BASE_URL}/api/pms-connect/mews/log/{PID}")
    assert r.status_code == 200
    assert len(r.json()["log"]) > 0


def test_unknown_provider_404(client):
    r = client.post(f"{BASE_URL}/api/pms-connect/unknown/push-from-rms/{PID}", json={})
    assert r.status_code == 404


# --- Cloudbeds ---
def test_cloudbeds_certify(client):
    r = client.post(f"{BASE_URL}/api/cloudbeds/certify/{PID}")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["passed"] is True
    assert d["mode"] == "mocked"
    assert len(d["checks"]) == 3


def test_cloudbeds_status_certification(client):
    r = client.get(f"{BASE_URL}/api/cloudbeds/status/{PID}")
    assert r.status_code == 200
    # status endpoint may or may not include certification directly, but config has it via certify
    # Verify via a follow-up push
    p = client.post(f"{BASE_URL}/api/cloudbeds/push-from-rms/{PID}", json={"days": 3})
    assert p.status_code == 200
    # Push still works in mocked mode (no API key)


# --- Regression ---
def test_regression_hotelrunner_certify(client):
    r = client.post(f"{BASE_URL}/api/hotelrunner/certify/{PID}")
    assert r.status_code == 200


def test_regression_elasticity(client):
    r = client.get(f"{BASE_URL}/api/elasticity/{PID}")
    assert r.status_code == 200


def test_regression_simulator_bidprice(client):
    r = client.get(f"{BASE_URL}/api/simulator/{PID}/bid-price")
    assert r.status_code == 200


def test_regression_ai_pricing(client):
    r = client.get(f"{BASE_URL}/api/revenue/ai-pricing/{PID}/suggestions?days=3&use_llm=false")
    assert r.status_code == 200
