"""Iteration 618: Certification Guide + Accounting Mapping tests."""
import os
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fallback for local envs — read from frontend/.env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.strip().split("=", 1)[1].rstrip("/")


def _login():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"},
                      timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    return j.get("access_token") or j.get("token")


TOKEN = None


def _h():
    global TOKEN
    if not TOKEN:
        TOKEN = _login()
    return {"Authorization": f"Bearer {TOKEN}"}


# --- Certification Guide ---
def test_cert_guide_shape():
    r = requests.get(f"{BASE_URL}/api/certifications/guide", headers=_h(), timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "items" in data and isinstance(data["items"], list)
    assert data["total"] == 8
    ids = [i["id"] for i in data["items"]]
    for want in ["booking", "expedia", "whatsapp", "resend", "stripe", "gbp", "sso", "accounting"]:
        assert want in ids, f"missing id {want}"
    for it in data["items"]:
        for k in ("title", "eta", "done", "url", "steps", "env"):
            assert k in it, f"missing key {k} in {it['id']}"
        assert isinstance(it["steps"], list) and len(it["steps"]) > 0
    assert "done" in data and "progress_pct" in data and "status" in data
    assert 0 <= data["progress_pct"] <= 100


# --- Accounting mapping ---
def test_accounting_mapping_qbo():
    pid = "aldgate-flats"
    r = requests.post(f"{BASE_URL}/api/accounting/mapping/qbo/{pid}",
                      headers=_h(), json={"revenue": "81", "bogus": "x"}, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ok"] is True
    assert data["mapping"]["revenue"] == "81"
    assert "bogus" not in data["mapping"]

    r2 = requests.get(f"{BASE_URL}/api/accounting/connectors/{pid}", headers=_h(), timeout=15)
    assert r2.status_code == 200, r2.text
    d2 = r2.json()
    assert d2["providers"]["qbo"]["mapping"]["revenue"] == "81"


def test_accounting_mapping_invalid_provider():
    r = requests.post(f"{BASE_URL}/api/accounting/mapping/foo/aldgate-flats",
                      headers=_h(), json={"revenue": "1"}, timeout=15)
    assert r.status_code == 404
